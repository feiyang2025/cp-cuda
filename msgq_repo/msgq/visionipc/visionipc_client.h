#pragma once

#include <set>
#include <string>

#include "msgq/ipc.h"
#include "msgq/visionipc/visionbuf.h"


class VisionIpcClient {
private:
  std::string name;
  Context * msg_ctx;
  SubSocket * sock;
  Poller * poller;
  // 上一次 recv 到的 buffer: 消费者只持有"最新一帧", 所以下一次 recv 时
  // 自动释放它 (消费者无需显式 release; 服务端写入前等的就是这个计数)。
  VisionBuf * prev_buf = nullptr;

public:
  bool connected = false;
  VisionStreamType type;
  int num_buffers = 0;
  VisionBuf buffers[VISIONIPC_MAX_FDS];
  VisionIpcClient(std::string name, VisionStreamType type, bool conflate);
  ~VisionIpcClient();
  VisionBuf * recv(VisionIpcBufExtra * extra=nullptr, const int timeout_ms=100);
  bool connect(bool blocking=true);
  bool is_connected() { return connected; }
  static std::set<VisionStreamType> getAvailableStreams(const std::string &name, bool blocking = true);
};
