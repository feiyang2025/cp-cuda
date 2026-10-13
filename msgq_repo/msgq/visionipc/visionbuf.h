#pragma once

#include <atomic>

#include "msgq/visionipc/visionipc.h"

#define VISIONBUF_SYNC_FROM_DEVICE 0
#define VISIONBUF_SYNC_TO_DEVICE 1

enum VisionStreamType {
  VISION_STREAM_ROAD,
  VISION_STREAM_DRIVER,
  VISION_STREAM_WIDE_ROAD,

  VISION_STREAM_MAP,
  VISION_STREAM_MAX,
};

class VisionBuf {
 public:
  // 共享引用计数: 客户端 recv 时 +1 (acquire), 用完 -1 (release);
  // server 端写前等待 ref_count==0, 防止"写未完成被读到"导致画面撕裂。
  // 指针指向本 buffer 映射内的元数据区 [frame_id(8B)][ref_count(8B)],
  // 由 server/client 各自从自己的映射地址算出, 因此跨进程有效。
  std::atomic<uint64_t> *ref_count = nullptr;

  void acquire() { if (ref_count) (*ref_count)++; }
  // Saturating decrement. The server force-resets ref_count to 0 when a buffer is held
  // past its timeout (see VisionIpcServer::get_buffer), which makes this client's later
  // release unbalanced. A plain `--` would then wrap the uint64 to 2**64-1, and the
  // server's next self-heal would have to walk ~1.8e19 decrements -- a spin that never
  // finishes and stalls the stream for good. Clamping at 0 keeps a late release a no-op.
  void release() {
    if (!ref_count) return;
    uint64_t cur = ref_count->load();
    while (cur > 0 && !ref_count->compare_exchange_weak(cur, cur - 1)) {}
  }
  uint64_t get_ref_count() { return ref_count ? ref_count->load() : 0; }
  // Hand the buffer back to the pool in one step. Only safe once the holder is known to be
  // gone, because a live holder will still be reading it.
  void reset_ref_count() { if (ref_count) ref_count->store(0); }

  size_t len = 0;
  size_t mmap_len = 0;
  void * addr = nullptr;
  uint64_t *frame_id;
  int fd = 0;

  size_t width = 0;
  size_t height = 0;
  size_t stride = 0;
  size_t uv_offset = 0;

  // YUV
  uint8_t * y = nullptr;
  uint8_t * uv = nullptr;

  // Visionipc
  uint64_t server_id = 0;
  size_t idx = 0;
  VisionStreamType type;

  // ion
  int handle = 0;

  void allocate(size_t len);
  void import();
  void init_yuv(size_t width, size_t height, size_t stride, size_t uv_offset);
  int sync(int dir);
  int free();

  void set_frame_id(uint64_t id);
  uint64_t get_frame_id();
};
