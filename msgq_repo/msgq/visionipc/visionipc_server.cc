#include <iostream>
#include <chrono>
#include <cassert>
#include <random>
#include <limits>
#include <chrono>
#include <string>
#include <thread>
#include <vector>

#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include "msgq/visionipc/visionipc.h"
#include "msgq/visionipc/visionipc_server.h"
#include "msgq/logger/logger.h"

std::string get_endpoint_name(std::string name, VisionStreamType type){
  return "visionipc_" + name + "_" + std::to_string(type);
}

std::string get_ipc_path(const std::string& name) {
  std::string path = "/tmp/";
  if (char* prefix = std::getenv("OPENPILOT_PREFIX")) {
    path += std::string(prefix) + "_";
  }
  return path + "visionipc_" + name;
}

VisionIpcServer::VisionIpcServer(std::string name_) : name(name_) {
  msg_ctx = Context::create();

  std::random_device rd("/dev/urandom");
  std::uniform_int_distribution<uint64_t> distribution(0, std::numeric_limits<uint64_t>::max());
  server_id = distribution(rd);
}

void VisionIpcServer::create_buffers(VisionStreamType type, size_t num_buffers, size_t width, size_t height){
  // TODO: assert that this type is not created yet
  assert(num_buffers < VISIONIPC_MAX_FDS);

  size_t size = width * height * 3 / 2;
  size_t stride = width;
  size_t uv_offset = width * height;

  create_buffers_with_sizes(type, num_buffers, width, height, size, stride, uv_offset);
}

void VisionIpcServer::create_buffers_with_sizes(VisionStreamType type, size_t num_buffers, size_t width, size_t height, size_t size, size_t stride, size_t uv_offset) {
  // Create map + alloc requested buffers
  for (size_t i = 0; i < num_buffers; i++){
    VisionBuf* buf = new VisionBuf();
    buf->allocate(size);
    buf->idx = i;
    buf->type = type;

    buf->init_yuv(width, height, stride, uv_offset);

    buffers[type].push_back(buf);
  }

  cur_idx[type] = 0;

  // Create msgq publisher for each of the `name` + type combos
  sockets[type] = PubSocket::create(msg_ctx, get_endpoint_name(name, type), false);
}


void VisionIpcServer::start_listener(){
  listener_thread = std::thread(&VisionIpcServer::listener, this);
}


void VisionIpcServer::listener(){
  LOGD("Starting listener for: %s", name.c_str());

  const std::string ipc_path = get_ipc_path(name);
  int sock = ipc_bind(ipc_path.c_str());
  assert(sock >= 0);

  while (!should_exit){
    // Wait for incoming connection
    struct pollfd polls[1] = {{0}};
    polls[0].fd = sock;
    polls[0].events = POLLIN;

    int ret = poll(polls, 1, 100);
    if (ret < 0) {
      if (errno == EINTR || errno == EAGAIN) continue;
      std::cout << "poll failed, stopping listener" << std::endl;
      break;
    }

    if (should_exit) break;
    if (!polls[0].revents) {
      continue;
    }

    // Handle incoming request
    int fd = accept(sock, NULL, NULL);
    assert(fd >= 0);

    VisionStreamType type = VisionStreamType::VISION_STREAM_MAX;
    int r = ipc_sendrecv_with_fds(false, fd, &type, sizeof(type), nullptr, 0, nullptr);
    if (r != sizeof(type)) {
      close(fd);
      if (should_exit) break;
      continue;
    }

    // send available stream types
    if (type == VisionStreamType::VISION_STREAM_MAX) {
      std::vector<VisionStreamType> available_stream_types;
      for (auto& [stream_type, _] : buffers) {
        available_stream_types.push_back(stream_type);
      }
      r = ipc_sendrecv_with_fds(true, fd, available_stream_types.data(), available_stream_types.size() * sizeof(VisionStreamType), nullptr, 0, nullptr);
      assert(r == available_stream_types.size() * sizeof(VisionStreamType));
      close(fd);
      continue;
    }

    if (buffers.count(type) <= 0) {
      std::cout << "got request for invalid buffer type: " << type << std::endl;
      close(fd);
      continue;
    }

    int fds[VISIONIPC_MAX_FDS] = {};
    int num_fds = buffers[type].size();
    VisionBuf bufs[VISIONIPC_MAX_FDS] = {};

    for (int i = 0; i < num_fds; i++){
      fds[i] = buffers[type][i]->fd;
      bufs[i] = *buffers[type][i];

      // Remove some private ion metadata
      bufs[i].handle = 0;

      bufs[i].server_id = server_id;
    }

    r = ipc_sendrecv_with_fds(true, fd, &bufs, sizeof(VisionBuf) * num_fds, fds, num_fds, nullptr);

    close(fd);
  }

  LOGD("Stopping listener for: %s", name.c_str());
  close(sock);
  unlink(ipc_path.c_str());
}



VisionBuf * VisionIpcServer::get_buffer(VisionStreamType type, int idx){
  // Do we want to keep track if the buffer has been sent out yet and warn user?
  assert(buffers.count(type));
  const auto &b = buffers[type];
  if (idx < 0) {
    idx = cur_idx[type]++ % b.size();
  } else {
    assert(idx < b.size() && idx >= 0);
    cur_idx[type] = idx;
  }

  VisionBuf * buf = b[idx];

  // 等待客户端读完该 buffer (ref_count==0) 再交给写入方, 防止"写未完成被读到"导致画面撕裂。
  // 超时 200ms 强制归零自愈: 客户端崩溃/被 SIGKILL 时 release() 不会执行, ref_count
  // 会永久停在 1; ref_count 位于共享内存、跨进程存活, 只"跳过"不修复 → 该缓冲被轮转
  // 命中时永远命中这条分支。这里强制把 ref_count 归零, 把缓冲归还池中, 使其可自愈。
  if (buf->get_ref_count() > 0) {
    auto start = std::chrono::steady_clock::now();
    while (buf->get_ref_count() > 0) {
      if (std::chrono::duration_cast<std::chrono::milliseconds>(
              std::chrono::steady_clock::now() - start).count() > 200) {
        uint64_t stuck = buf->get_ref_count();
        // One atomic store, never a decrement loop. A loop has to walk the whole
        // counter down, so a counter that has already wrapped (a late release
        // arriving after an earlier reset) turns this into an unbounded spin that
        // never yields a frame again. The store is idempotent and O(1).
        buf->reset_ref_count();
        LOGE("get_buffer: buffer idx=%zu type=%d busy for >200ms (ref=%llu), ref_count reset",
             buf->idx, (int)type, (unsigned long long)stuck);
        break;
      }
      std::this_thread::sleep_for(std::chrono::microseconds(200));
    }
  }

  return buf;
}

void VisionIpcServer::send(VisionBuf * buf, VisionIpcBufExtra * extra, bool sync){
  if (sync) {
    if (buf->sync(VISIONBUF_SYNC_FROM_DEVICE) != 0) {
      LOGE("Failed to sync buffer");
    }
  }
  assert(buffers.count(buf->type));
  assert(buf->idx < buffers[buf->type].size());

  // Send over correct msgq socket
  VisionIpcPacket packet = {0};
  packet.server_id = server_id;
  packet.idx = buf->idx;
  packet.extra = *extra;

  sockets[buf->type]->send((char*)&packet, sizeof(packet));
}

VisionIpcServer::~VisionIpcServer(){
  should_exit = true;
  if (listener_thread.joinable()) {
    int sock = ipc_connect(get_ipc_path(name).c_str());
    if (sock >= 0) {
      close(sock);
    }
    listener_thread.join();
  }

  // VisionBuf cleanup
  for (auto const& [type, buf] : buffers) {
    for (VisionBuf* b : buf){
      if (b->free() != 0) {
        LOGE("Failed to free buffer");
      }
      delete b;
    }
  }

  // Messaging cleanup
  for (auto const& [type, sock] : sockets) {
    delete sock;
  }
  delete msg_ctx;
}
