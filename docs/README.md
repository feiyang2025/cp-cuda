# 文档索引

本文件是 `docs/` 的导航页。**不修改也不移动任何现有文档**；分类只在这一页里表达。

当前共 **120** 篇 markdown（长期参考 16，带日期的实验记录 61，未标日期的实验记录 43）。

> **为什么不合并成一篇**：实验记录的价值在于「哪一天、在哪台车、什么条件下得出的结论」。
> 合并会毁掉证据链，而且「按车型分」和「按主题分」天然冲突——同一主题横跨多台车，
> 同一台车又横跨多个主题，合并必然丢一边。

## 目录

- [一、按类型](#一按类型)
- [二、按主题](#二按主题)
- [三、AGENTS.md 点名的文档](#三agentsmd-点名的文档)
- [四、元信息约定](#四元信息约定待补)

## 一、按类型

### 长期参考（改代码时需要查）

这些是持续有效的技术参考，不是某次实验的产物。

#### 上游 commaai 资产（不建议改动）

- [`docs/CARS.md`](docs/CARS.md) — Supported Cars
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — How to contribute
- [`docs/DEBUGGING_SAFETY.md`](docs/DEBUGGING_SAFETY.md) — Debugging Panda Safety with Replay Drive + LLDB
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — Docs development
- [`docs/INSTALL-WINDOWS-KO.md`](docs/INSTALL-WINDOWS-KO.md) — 🥕 Jetson 설치 안내
- [`docs/INTEGRATION.md`](docs/INTEGRATION.md) — Integration with Stock Features
- [`docs/JETSON-SSH.md`](docs/JETSON-SSH.md) — Jetson SSH 접속 안내
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — Limitations
- [`docs/SAFETY.md`](docs/SAFETY.md) — Safety
- [`docs/index.md`](docs/index.md) — What is openpilot?

#### 本项目技术参考

- [`docs/big_model_local_gpu_baseline.md`](docs/big_model_local_gpu_baseline.md) — 本机大模型性能基线与已知陷阱
- [`docs/carrot_navi_7713_7714_deceleration.md`](docs/carrot_navi_7713_7714_deceleration.md) — 7713 / 7714 내비 감속 적용 비교
- [`docs/carrot_navi_7714_branch_comparison.md`](docs/carrot_navi_7714_branch_comparison.md) — 7714 내비 감속 브랜치 비교
- [`docs/cinque_v2_model.md`](docs/cinque_v2_model.md) — Cinque v2 model integration
- [`docs/cinque_v3_model.md`](docs/cinque_v3_model.md) — Cinque v3 experiment
- [`docs/cluster_road_camera_map_flicker_analysis.md`](docs/cluster_road_camera_map_flicker_analysis.md) — Cluster 도로 카메라 선택 시 지도 영역 카메라 깜빡임 분석

### 实验记录 — 带日期（61 篇）

按时间倒序。每条结论都应连同其日期一起解读。

**2026-10**

- [`docs/egpu_usb_recurrence_20261010.md`](docs/egpu_usb_recurrence_20261010.md) — Recurrent eGPU USB failures, 2026-10-10（2026-10-10）
- [`docs/ioniq5_signal_head_trial_20261010.md`](docs/ioniq5_signal_head_trial_20261010.md) — 내부 ONNX 신호 예측 학습 1차 실험 — 2026-10-10（2026-10-10）
- [`docs/rav4_steering_20261010.md`](docs/rav4_steering_20261010.md) — RAV4 steering activation and event-cadence regression — 2026-10-10（2026-10-10）
- [`docs/sonata_92_startup_steering_20261010.md`](docs/sonata_92_startup_steering_20261010.md) — Sonata 2024 startup steering step — 2026-10-10 investigation（2026-10-10）
- [`docs/egpu_psp_rejection_20261009.md`](docs/egpu_psp_rejection_20261009.md) — egpu_psp_rejection_20261009（2026-10-09）
- [`docs/egpu_status_guidance_20261009.md`](docs/egpu_status_guidance_20261009.md) — eGPU Web status guidance (2026-10-09)（2026-10-09）
- [`docs/hud_camera_startup_20261009.md`](docs/hud_camera_startup_20261009.md) — HUD reconnection and camera startup stalls（2026-10-09）
- [`docs/pr536_review_20261009.md`](docs/pr536_review_20261009.md) — PR #536 review and integration（2026-10-09）
- [`docs/rav4_acc_20261009.md`](docs/rav4_acc_20261009.md) — RAV4 TSS2 2022 cruise investigation — 2026-10-09（2026-10-09）
- [`docs/egpu_usb_rejection_20261008.md`](docs/egpu_usb_rejection_20261008.md) — eGPU USB transfer failure incorrectly rejected a model（2026-10-08）
- [`docs/mdm2_20261008.md`](docs/mdm2_20261008.md) — Mountain Dew 870a4823 on carrot-mdm2（2026-10-08）
- [`docs/egpu_startup_selection_20261007.md`](docs/egpu_startup_selection_20261007.md) — eGPU model selection before startup, October 7, 2026（2026-10-07）
- [`docs/jetlink_pr534_review_20261007.md`](docs/jetlink_pr534_review_20261007.md) — PR #534: existing Jetson and eGPU compatibility（2026-10-07）
- [`docs/jetson_boot_update_20261007.md`](docs/jetson_boot_update_20261007.md) — Jetson boot update and first-time transition（2026-10-07）
- [`docs/jetson_offline_boot_patch_20261007.md`](docs/jetson_offline_boot_patch_20261007.md) — One-time Windows patch for automatic Jetson updates（2026-10-07）
- [`docs/ioniq5_1044_hotplug_20261006.md`](docs/ioniq5_1044_hotplug_20261006.md) — Ioniq 5 PE Jetson/HUD hotplug, 2026-10-06（2026-10-06）
- [`docs/jetlink_v3_compatibility_20261006.md`](docs/jetlink_v3_compatibility_20261006.md) — Jetlink v2/v3 compatibility — 2026-10-06（2026-10-06）
- [`docs/jetson_hud_temperature_20261006.md`](docs/jetson_hud_temperature_20261006.md) — Jetson HUD activation and temperature, 2026-10-06（2026-10-06）
- [`docs/build_time_floor_20261005.md`](docs/build_time_floor_20261005.md) — Offline build clock floor — 2026-10-05（2026-10-05）
- [`docs/ioniq5_103d_late_lead_20261005.md`](docs/ioniq5_103d_late_lead_20261005.md) — Ioniq 5 PE 103d: 전방 저속 물체 선택 지연 검토（2026-10-05）
- [`docs/longitudinal_gap_hold_band_20261005.md`](docs/longitudinal_gap_hold_band_20261005.md) — Distance range for additional following-headroom hold（2026-10-05）
- [`docs/hud_web_camera_20261004.md`](docs/hud_web_camera_20261004.md) — External HUD and Carrot Web camera concurrency（2026-10-04）
- [`docs/longitudinal_jerk_cost_trial_20261004.md`](docs/longitudinal_jerk_cost_trial_20261004.md) — ACC jerk-cost driving trial（2026-10-04）
- [`docs/casper_c3_ui_20261003.md`](docs/casper_c3_ui_20261003.md) — Casper EV C3 UI frame-rate analysis — 2026-10-03（2026-10-03）
- [`docs/casper_c3_ui_after_20261003.md`](docs/casper_c3_ui_after_20261003.md) — Casper C3 follow-up: a0f1a004 UI frame-rate complaint（2026-10-03）
- [`docs/casper_c3_ui_geometry_20261003.md`](docs/casper_c3_ui_geometry_20261003.md) — C3/C4 path and tire geometry batching (2026-10-03)（2026-10-03）
- [`docs/casper_c3_ui_native_pss_20261003.md`](docs/casper_c3_ui_native_pss_20261003.md) — Casper C3: spread memory accounting and evaluate native UI work（2026-10-03）
- [`docs/casper_c3_ui_optimization_review_20261003.md`](docs/casper_c3_ui_optimization_review_20261003.md) — Casper C3 CPU and UI optimization review — 2026-10-03（2026-10-03）
- [`docs/id4_dm_enable_cadence_20261003.md`](docs/id4_dm_enable_cadence_20261003.md) — ID.4 DM re-enable communication fault — 2026-10-03（2026-10-03）
- [`docs/tucson_30c_left_steering_20261003.md`](docs/tucson_30c_left_steering_20261003.md) — Tucson straight-road left steering near a vehicle transporter（2026-10-03）
- [`docs/ui_reuse_optimization_20261003.md`](docs/ui_reuse_optimization_20261003.md) — C3/C4 UI reuse and projection batching — 2026-10-03（2026-10-03）
- [`docs/ui_text_optimization_20261003.md`](docs/ui_text_optimization_20261003.md) — C3/C4 text, shader and recording cost reduction (2026-10-03)（2026-10-03）
- [`docs/ioniq5_5d7_steering_20261002.md`](docs/ioniq5_5d7_steering_20261002.md) — Ioniq 5 PE 5d7: reduced steering authority and missed handover（2026-10-02）
- [`docs/native_cpu_experiment_20261002.md`](docs/native_cpu_experiment_20261002.md) — Native CPU experiment, 2026-10-02（2026-10-02）
- [`docs/dm_cluster_alerts_20261001.md`](docs/dm_cluster_alerts_20261001.md) — DM startup notice and Hyundai/Kia cluster warnings — 2026-10-01（2026-10-01）
- [`docs/scc_longitudinal_lead_20261001.md`](docs/scc_longitudinal_lead_20261001.md) — SCC longitudinal lead continuity (2026-10-01)（2026-10-01）

**2026-09**

- [`docs/id4_steering_model_comparison_20260930.md`](docs/id4_steering_model_comparison_20260930.md) — ID.4 same-road model and learned-parameter comparison（2026-09-30）
- [`docs/ioniq5_pe_cluster_warning_20260930.md`](docs/ioniq5_pe_cluster_warning_20260930.md) — Ioniq 5 PE intermittent driver-assistance cluster warning（2026-09-30）
- [`docs/steering_handover_20260930.md`](docs/steering_handover_20260930.md) — Experimental Hyundai angle-steering handover（2026-09-30）
- [`docs/steering_handover_ff6_ff7_20260930.md`](docs/steering_handover_ff6_ff7_20260930.md) — Ioniq 5 PE handover trial: delayed recovery after force release（2026-09-30）
- [`docs/dm_traffic_hold_20260929.md`](docs/dm_traffic_hold_20260929.md) — DM hold on first surrounding traffic（2026-09-29）
- [`docs/impact_dashcam_20260929.md`](docs/impact_dashcam_20260929.md) — Suspected-impact Dashcam transition（2026-09-29）
- [`docs/jetlink_ff1_investigation_20260929.md`](docs/jetlink_ff1_investigation_20260929.md) — Ioniq 5 PE ff1 startup and process alert, 2026-09-29（2026-09-29）
- [`docs/reboot_sound_20260929.md`](docs/reboot_sound_20260929.md) — Reboot notification sound（2026-09-29）
- [`docs/system_ready_sound_20260929.md`](docs/system_ready_sound_20260929.md) — Onroad readiness sound（2026-09-29）
- [`docs/dm_onroad_preview_20260928.md`](docs/dm_onroad_preview_20260928.md) — Passive onroad driver-monitoring inset（2026-09-28）
- [`docs/dm_reader_crash_20260928.md`](docs/dm_reader_crash_20260928.md) — DM road-context reader crash — 2026-09-28（2026-09-28）
- [`docs/ev9_tentative_front_lead_20260928.md`](docs/ev9_tentative_front_lead_20260928.md) — EV9 tentative front-radar false lead, 2026-09-28（2026-09-28）
- [`docs/jetlink_apple_feasibility_20260928.md`](docs/jetlink_apple_feasibility_20260928.md) — Jetlink Mac and iPhone interoperability review（2026-09-28）
- [`docs/jetson_windows_installer_20260928.md`](docs/jetson_windows_installer_20260928.md) — Jetson Windows 설치 패키지 검증 기록（2026-09-28）
- [`docs/lfs_to_git_20260928.md`](docs/lfs_to_git_20260928.md) — Ordinary Git artifact storage, 2026-09-28（2026-09-28）
- [`docs/sonata_stopping_lead_continuity_20260928.md`](docs/sonata_stopping_lead_continuity_20260928.md) — Sonata braking lead continuity (2026-09-28)（2026-09-28）
- [`docs/ioniq5_stock_hud_flicker_20260927.md`](docs/ioniq5_stock_hud_flicker_20260927.md) — Ioniq 5 stock HUD / cluster lead-color flicker（2026-09-27）
- [`docs/jetson_wip_integration_20260927.md`](docs/jetson_wip_integration_20260927.md) — Jetson 기능의 carrot-wip 통합 — 2026-09-27（2026-09-27）
- [`docs/ioniq5_acceleration_20260926.md`](docs/ioniq5_acceleration_20260926.md) — Ioniq 5 acceleration oscillation, 2026-09-26（2026-09-26）
- [`docs/ioniq9_can_startup_20260926.md`](docs/ioniq9_can_startup_20260926.md) — Ioniq 9 startup CAN/SPI failure, 2026-09-26（2026-09-26）
- [`docs/carnival_stopping_path_endpoint_20260925.md`](docs/carnival_stopping_path_endpoint_20260925.md) — Carnival braking interruption from a short stopping-path endpoint（2026-09-25）
- [`docs/boot_latency_20260924.md`](docs/boot_latency_20260924.md) — Ioniq 5 C4 startup after the September 24 update（2026-09-24）
- [`docs/camera_sof_gap_20260923.md`](docs/camera_sof_gap_20260923.md) — Ioniq 5 camera SOF gap and startup phase mismatch（2026-09-23）
- [`docs/lead_braking_tau_20260923.md`](docs/lead_braking_tau_20260923.md) — Jerk-confirmed lead braking persistence（2026-09-23）
- [`docs/cinque_v3_integration_20260919.md`](docs/cinque_v3_integration_20260919.md) — Cinque v3 integration and upstream review, 2026-09-19（2026-09-19）

### 实验记录 — 未标日期（43 篇）

这些是一次性实验记录，只是文件名没有日期后缀。**引用结论时请连同文件名里的日期/车型一起看。**

- [`docs/README.md`](docs/README.md) — 文档索引
- [`docs/agnos_19_8_bluetooth_trial.md`](docs/agnos_19_8_bluetooth_trial.md) — AGNOS 19.8 native Bluetooth / Cinque v3 experiment
- [`docs/c3_preupload_warp.md`](docs/c3_preupload_warp.md) — C3 pre-upload camera warp
- [`docs/camera_core5_trial.md`](docs/camera_core5_trial.md) — Camera CPU placement trials
- [`docs/canfd_cluster_rx_forwarding.md`](docs/canfd_cluster_rx_forwarding.md) — CAN-FD cluster forwarding on stock reception (2026-09-30)
- [`docs/canfd_feedback_counters.md`](docs/canfd_feedback_counters.md) — CAN-FD camera feedback counters
- [`docs/carrot_radar_interrupted_vision_validation.md`](docs/carrot_radar_interrupted_vision_validation.md) — Interrupted stationary confirmation, 2026-09-05
- [`docs/carrot_radar_moving_front_range_validation.md`](docs/carrot_radar_moving_front_range_validation.md) — Moving front radar and uncertain vision range, 2026-09-05
- [`docs/carrot_radar_moving_vision_stationary_validation.md`](docs/carrot_radar_moving_vision_stationary_validation.md) — Moving-vision / stationary-reflection review, 2026-09-05
- [`docs/carrot_radar_stationary_confirmation_validation.md`](docs/carrot_radar_stationary_confirmation_validation.md) — Stationary front-radar confirmation review — 2026-09-05
- [`docs/carrot_radar_stationary_position_evidence_validation.md`](docs/carrot_radar_stationary_position_evidence_validation.md) — 정지차 위치 이력·코너 교차 확인 검증
- [`docs/carrot_stopping_experiment.md`](docs/carrot_stopping_experiment.md) — CAN FD 정지 제어: carrot-stopping 시험 및 carrot-wip 반영
- [`docs/carrot_web_upload.md`](docs/carrot_web_upload.md) — Carrot web upload
- [`docs/cruise_coasting.md`](docs/cruise_coasting.md) — Cruise coasting margin
- [`docs/driver_monitoring_dm2.md`](docs/driver_monitoring_dm2.md) — DM2 implementation and validation - 2026-09-28
- [`docs/driving_mode_recovery.md`](docs/driving_mode_recovery.md) — Automatic driving-mode recovery
- [`docs/ev5_cluster_corner_display.md`](docs/ev5_cluster_corner_display.md) — EV5 cluster corner-object visibility (2026-09-24)
- [`docs/jetlink_boot_optimization.md`](docs/jetlink_boot_optimization.md) — Jetson dedicated-appliance boot investigation
- [`docs/jetlink_deployment_review.md`](docs/jetlink_deployment_review.md) — Jetson 배포 자동화 검토 — 2026-09-25
- [`docs/jetlink_experiment.md`](docs/jetlink_experiment.md) — Carrot Jetlink experiment
- [`docs/jetlink_mac_testing.md`](docs/jetlink_mac_testing.md) — Mac Jetlink 연결 시험
- [`docs/jetlink_protocol3_compatibility.md`](docs/jetlink_protocol3_compatibility.md) — Jetlink protocol 3 compatibility
- [`docs/jetlink_ready_investigation.md`](docs/jetlink_ready_investigation.md) — Jetlink READY reconnect investigation, September 26, 2026
- [`docs/jetlink_sd_image.md`](docs/jetlink_sd_image.md) — Jetson SD image candidate and update design
- [`docs/jetlink_updates.md`](docs/jetlink_updates.md) — Jetson health and application updates
- [`docs/jetson_power_loss_protection.md`](docs/jetson_power_loss_protection.md) — Jetson storage protection candidate (2026-09-28)
- [`docs/jetson_sd_nvme_patch.md`](docs/jetson_sd_nvme_patch.md) — Jetson microSD / NVMe 공용 패치
- [`docs/lane_change_gap_validation.md`](docs/lane_change_gap_validation.md) — Lane-change following-distance control
- [`docs/meb_radar_distance_alignment.md`](docs/meb_radar_distance_alignment.md) — VW MEB distance alignment
- [`docs/onroad_initialization_timeout.md`](docs/onroad_initialization_timeout.md) — Onroad initialization grace period
- [`docs/os04c10_exposure_investigation.md`](docs/os04c10_exposure_investigation.md) — OS04C10 exposure update / camera gap investigation, 2026-09-24
- [`docs/radar_bridge_joint_scc_false_lead.md`](docs/radar_bridge_joint_scc_false_lead.md) — 교량 이음새 구간의 SCC 보조 리드 오승인
- [`docs/radar_cutin_outer_body_review.md`](docs/radar_cutin_outer_body_review.md) — Near-field outer-body CUT-IN review (2026-09-06)
- [`docs/radar_cutout_validation.md`](docs/radar_cutout_validation.md) — Predicted lead departure: bounded ACC headway relief
- [`docs/radar_ev9_stationary_pair_cutin.md`](docs/radar_ev9_stationary_pair_cutin.md) — EV9 roadside false CUT-IN, 2026-09-23
- [`docs/radar_front_position_history.md`](docs/radar_front_position_history.md) — Earlier stationary L1 acquisition from continuous visual/front position evidence
- [`docs/radar_lead_acceleration_filter.md`](docs/radar_lead_acceleration_filter.md) — Noise-aware lead acceleration observer
- [`docs/radar_process_isolation.md`](docs/radar_process_isolation.md) — Radar preprocessing isolation and equivalent-output optimization
- [`docs/radar_slow_body_entry_validation.md`](docs/radar_slow_body_entry_validation.md) — Slow near-body cut-in with moving model path (2026-09-11)
- [`docs/radar_track_flip.md`](docs/radar_track_flip.md) — Per-vehicle front-radar lateral orientation
- [`docs/staria_ev_registration.md`](docs/staria_ev_registration.md) — Hyundai Staria EV 2026 registration
- [`docs/startup_recovery.md`](docs/startup_recovery.md) — Startup update recovery — 2026-09-28
- [`docs/xiaoge_onroad_startup.md`](docs/xiaoge_onroad_startup.md) — Xiaoge onroad startup

## 二、按主题

**同一篇会出现在两处**：第一节按「类型」归类，第二节按「主题」归类，不是重复。
主题内每篇只出现一次；跨主题的按主要用途归到其中一个。

### 雷达 / 目标跟踪（17 篇，其中长期参考 0）

- [`docs/ev9_tentative_front_lead_20260928.md`](docs/ev9_tentative_front_lead_20260928.md) — EV9 tentative front-radar false lead, 2026-09-28（2026-09-28）
- [`docs/lead_braking_tau_20260923.md`](docs/lead_braking_tau_20260923.md) — Jerk-confirmed lead braking persistence（2026-09-23）
- [`docs/radar_track_flip.md`](docs/radar_track_flip.md) — Per-vehicle front-radar lateral orientation
- [`docs/radar_slow_body_entry_validation.md`](docs/radar_slow_body_entry_validation.md) — Slow near-body cut-in with moving model path (2026-09-11)
- [`docs/radar_process_isolation.md`](docs/radar_process_isolation.md) — Radar preprocessing isolation and equivalent-output optimization
- [`docs/radar_lead_acceleration_filter.md`](docs/radar_lead_acceleration_filter.md) — Noise-aware lead acceleration observer
- [`docs/radar_front_position_history.md`](docs/radar_front_position_history.md) — Earlier stationary L1 acquisition from continuous visual/front position evidence
- [`docs/radar_ev9_stationary_pair_cutin.md`](docs/radar_ev9_stationary_pair_cutin.md) — EV9 roadside false CUT-IN, 2026-09-23
- [`docs/radar_cutout_validation.md`](docs/radar_cutout_validation.md) — Predicted lead departure: bounded ACC headway relief
- [`docs/radar_cutin_outer_body_review.md`](docs/radar_cutin_outer_body_review.md) — Near-field outer-body CUT-IN review (2026-09-06)
- [`docs/radar_bridge_joint_scc_false_lead.md`](docs/radar_bridge_joint_scc_false_lead.md) — 교량 이음새 구간의 SCC 보조 리드 오승인
- [`docs/meb_radar_distance_alignment.md`](docs/meb_radar_distance_alignment.md) — VW MEB distance alignment
- [`docs/carrot_radar_stationary_position_evidence_validation.md`](docs/carrot_radar_stationary_position_evidence_validation.md) — 정지차 위치 이력·코너 교차 확인 검증
- [`docs/carrot_radar_stationary_confirmation_validation.md`](docs/carrot_radar_stationary_confirmation_validation.md) — Stationary front-radar confirmation review — 2026-09-05
- [`docs/carrot_radar_moving_vision_stationary_validation.md`](docs/carrot_radar_moving_vision_stationary_validation.md) — Moving-vision / stationary-reflection review, 2026-09-05
- [`docs/carrot_radar_moving_front_range_validation.md`](docs/carrot_radar_moving_front_range_validation.md) — Moving front radar and uncertain vision range, 2026-09-05
- [`docs/carrot_radar_interrupted_vision_validation.md`](docs/carrot_radar_interrupted_vision_validation.md) — Interrupted stationary confirmation, 2026-09-05

### eGPU / 大模型 / modeld（10 篇，其中长期参考 3）

- [`docs/egpu_usb_recurrence_20261010.md`](docs/egpu_usb_recurrence_20261010.md) — Recurrent eGPU USB failures, 2026-10-10（2026-10-10）
- [`docs/egpu_status_guidance_20261009.md`](docs/egpu_status_guidance_20261009.md) — eGPU Web status guidance (2026-10-09)（2026-10-09）
- [`docs/egpu_psp_rejection_20261009.md`](docs/egpu_psp_rejection_20261009.md) — egpu_psp_rejection_20261009（2026-10-09）
- [`docs/mdm2_20261008.md`](docs/mdm2_20261008.md) — Mountain Dew 870a4823 on carrot-mdm2（2026-10-08）
- [`docs/egpu_usb_rejection_20261008.md`](docs/egpu_usb_rejection_20261008.md) — eGPU USB transfer failure incorrectly rejected a model（2026-10-08）
- [`docs/egpu_startup_selection_20261007.md`](docs/egpu_startup_selection_20261007.md) — eGPU model selection before startup, October 7, 2026（2026-10-07）
- [`docs/cinque_v3_integration_20260919.md`](docs/cinque_v3_integration_20260919.md) — Cinque v3 integration and upstream review, 2026-09-19（2026-09-19）
- [`docs/cinque_v3_model.md`](docs/cinque_v3_model.md) — Cinque v3 experiment
- [`docs/cinque_v2_model.md`](docs/cinque_v2_model.md) — Cinque v2 model integration
- [`docs/big_model_local_gpu_baseline.md`](docs/big_model_local_gpu_baseline.md) — 本机大模型性能基线与已知陷阱

### Jetlink 投屏（12 篇，其中长期参考 0）

- [`docs/jetlink_pr534_review_20261007.md`](docs/jetlink_pr534_review_20261007.md) — PR #534: existing Jetson and eGPU compatibility（2026-10-07）
- [`docs/jetlink_v3_compatibility_20261006.md`](docs/jetlink_v3_compatibility_20261006.md) — Jetlink v2/v3 compatibility — 2026-10-06（2026-10-06）
- [`docs/jetlink_ff1_investigation_20260929.md`](docs/jetlink_ff1_investigation_20260929.md) — Ioniq 5 PE ff1 startup and process alert, 2026-09-29（2026-09-29）
- [`docs/jetlink_apple_feasibility_20260928.md`](docs/jetlink_apple_feasibility_20260928.md) — Jetlink Mac and iPhone interoperability review（2026-09-28）
- [`docs/jetlink_updates.md`](docs/jetlink_updates.md) — Jetson health and application updates
- [`docs/jetlink_sd_image.md`](docs/jetlink_sd_image.md) — Jetson SD image candidate and update design
- [`docs/jetlink_ready_investigation.md`](docs/jetlink_ready_investigation.md) — Jetlink READY reconnect investigation, September 26, 2026
- [`docs/jetlink_protocol3_compatibility.md`](docs/jetlink_protocol3_compatibility.md) — Jetlink protocol 3 compatibility
- [`docs/jetlink_mac_testing.md`](docs/jetlink_mac_testing.md) — Mac Jetlink 연결 시험
- [`docs/jetlink_experiment.md`](docs/jetlink_experiment.md) — Carrot Jetlink experiment
- [`docs/jetlink_deployment_review.md`](docs/jetlink_deployment_review.md) — Jetson 배포 자동화 검토 — 2026-09-25
- [`docs/jetlink_boot_optimization.md`](docs/jetlink_boot_optimization.md) — Jetson dedicated-appliance boot investigation

### Jetson 硬件与部署（12 篇，其中长期参考 0）

- [`docs/jetson_offline_boot_patch_20261007.md`](docs/jetson_offline_boot_patch_20261007.md) — One-time Windows patch for automatic Jetson updates（2026-10-07）
- [`docs/jetson_boot_update_20261007.md`](docs/jetson_boot_update_20261007.md) — Jetson boot update and first-time transition（2026-10-07）
- [`docs/jetson_hud_temperature_20261006.md`](docs/jetson_hud_temperature_20261006.md) — Jetson HUD activation and temperature, 2026-10-06（2026-10-06）
- [`docs/native_cpu_experiment_20261002.md`](docs/native_cpu_experiment_20261002.md) — Native CPU experiment, 2026-10-02（2026-10-02）
- [`docs/lfs_to_git_20260928.md`](docs/lfs_to_git_20260928.md) — Ordinary Git artifact storage, 2026-09-28（2026-09-28）
- [`docs/jetson_windows_installer_20260928.md`](docs/jetson_windows_installer_20260928.md) — Jetson Windows 설치 패키지 검증 기록（2026-09-28）
- [`docs/jetson_wip_integration_20260927.md`](docs/jetson_wip_integration_20260927.md) — Jetson 기능의 carrot-wip 통합 — 2026-09-27（2026-09-27）
- [`docs/boot_latency_20260924.md`](docs/boot_latency_20260924.md) — Ioniq 5 C4 startup after the September 24 update（2026-09-24）
- [`docs/os04c10_exposure_investigation.md`](docs/os04c10_exposure_investigation.md) — OS04C10 exposure update / camera gap investigation, 2026-09-24
- [`docs/jetson_sd_nvme_patch.md`](docs/jetson_sd_nvme_patch.md) — Jetson microSD / NVMe 공용 패치
- [`docs/jetson_power_loss_protection.md`](docs/jetson_power_loss_protection.md) — Jetson storage protection candidate (2026-09-28)
- [`docs/agnos_19_8_bluetooth_trial.md`](docs/agnos_19_8_bluetooth_trial.md) — AGNOS 19.8 native Bluetooth / Cinque v3 experiment

### 相机与图像通路（3 篇，其中长期参考 0）

- [`docs/camera_sof_gap_20260923.md`](docs/camera_sof_gap_20260923.md) — Ioniq 5 camera SOF gap and startup phase mismatch（2026-09-23）
- [`docs/camera_core5_trial.md`](docs/camera_core5_trial.md) — Camera CPU placement trials
- [`docs/c3_preupload_warp.md`](docs/c3_preupload_warp.md) — C3 pre-upload camera warp

### CAN / 集群通信（2 篇，其中长期参考 0）

- [`docs/canfd_feedback_counters.md`](docs/canfd_feedback_counters.md) — CAN-FD camera feedback counters
- [`docs/canfd_cluster_rx_forwarding.md`](docs/canfd_cluster_rx_forwarding.md) — CAN-FD cluster forwarding on stock reception (2026-09-30)

### DM / UI / HUD（15 篇，其中长期参考 0）

- [`docs/hud_camera_startup_20261009.md`](docs/hud_camera_startup_20261009.md) — HUD reconnection and camera startup stalls（2026-10-09）
- [`docs/hud_web_camera_20261004.md`](docs/hud_web_camera_20261004.md) — External HUD and Carrot Web camera concurrency（2026-10-04）
- [`docs/ui_text_optimization_20261003.md`](docs/ui_text_optimization_20261003.md) — C3/C4 text, shader and recording cost reduction (2026-10-03)（2026-10-03）
- [`docs/ui_reuse_optimization_20261003.md`](docs/ui_reuse_optimization_20261003.md) — C3/C4 UI reuse and projection batching — 2026-10-03（2026-10-03）
- [`docs/casper_c3_ui_optimization_review_20261003.md`](docs/casper_c3_ui_optimization_review_20261003.md) — Casper C3 CPU and UI optimization review — 2026-10-03（2026-10-03）
- [`docs/casper_c3_ui_native_pss_20261003.md`](docs/casper_c3_ui_native_pss_20261003.md) — Casper C3: spread memory accounting and evaluate native UI work（2026-10-03）
- [`docs/casper_c3_ui_geometry_20261003.md`](docs/casper_c3_ui_geometry_20261003.md) — C3/C4 path and tire geometry batching (2026-10-03)（2026-10-03）
- [`docs/casper_c3_ui_after_20261003.md`](docs/casper_c3_ui_after_20261003.md) — Casper C3 follow-up: a0f1a004 UI frame-rate complaint（2026-10-03）
- [`docs/casper_c3_ui_20261003.md`](docs/casper_c3_ui_20261003.md) — Casper EV C3 UI frame-rate analysis — 2026-10-03（2026-10-03）
- [`docs/dm_cluster_alerts_20261001.md`](docs/dm_cluster_alerts_20261001.md) — DM startup notice and Hyundai/Kia cluster warnings — 2026-10-01（2026-10-01）
- [`docs/dm_traffic_hold_20260929.md`](docs/dm_traffic_hold_20260929.md) — DM hold on first surrounding traffic（2026-09-29）
- [`docs/dm_reader_crash_20260928.md`](docs/dm_reader_crash_20260928.md) — DM road-context reader crash — 2026-09-28（2026-09-28）
- [`docs/dm_onroad_preview_20260928.md`](docs/dm_onroad_preview_20260928.md) — Passive onroad driver-monitoring inset（2026-09-28）
- [`docs/xiaoge_onroad_startup.md`](docs/xiaoge_onroad_startup.md) — Xiaoge onroad startup
- [`docs/driver_monitoring_dm2.md`](docs/driver_monitoring_dm2.md) — DM2 implementation and validation - 2026-09-28

### 纵向 / 转向 / 跟车（11 篇，其中长期参考 0）

- [`docs/sonata_92_startup_steering_20261010.md`](docs/sonata_92_startup_steering_20261010.md) — Sonata 2024 startup steering step — 2026-10-10 investigation（2026-10-10）
- [`docs/rav4_steering_20261010.md`](docs/rav4_steering_20261010.md) — RAV4 steering activation and event-cadence regression — 2026-10-10（2026-10-10）
- [`docs/rav4_acc_20261009.md`](docs/rav4_acc_20261009.md) — RAV4 TSS2 2022 cruise investigation — 2026-10-09（2026-10-09）
- [`docs/longitudinal_gap_hold_band_20261005.md`](docs/longitudinal_gap_hold_band_20261005.md) — Distance range for additional following-headroom hold（2026-10-05）
- [`docs/longitudinal_jerk_cost_trial_20261004.md`](docs/longitudinal_jerk_cost_trial_20261004.md) — ACC jerk-cost driving trial（2026-10-04）
- [`docs/tucson_30c_left_steering_20261003.md`](docs/tucson_30c_left_steering_20261003.md) — Tucson straight-road left steering near a vehicle transporter（2026-10-03）
- [`docs/steering_handover_ff6_ff7_20260930.md`](docs/steering_handover_ff6_ff7_20260930.md) — Ioniq 5 PE handover trial: delayed recovery after force release（2026-09-30）
- [`docs/steering_handover_20260930.md`](docs/steering_handover_20260930.md) — Experimental Hyundai angle-steering handover（2026-09-30）
- [`docs/sonata_stopping_lead_continuity_20260928.md`](docs/sonata_stopping_lead_continuity_20260928.md) — Sonata braking lead continuity (2026-09-28)（2026-09-28）
- [`docs/lane_change_gap_validation.md`](docs/lane_change_gap_validation.md) — Lane-change following-distance control
- [`docs/cruise_coasting.md`](docs/cruise_coasting.md) — Cruise coasting margin

### 导航协议 7713/7714（2 篇，其中长期参考 2）

- [`docs/carrot_navi_7714_branch_comparison.md`](docs/carrot_navi_7714_branch_comparison.md) — 7714 내비 감속 브랜치 비교
- [`docs/carrot_navi_7713_7714_deceleration.md`](docs/carrot_navi_7713_7714_deceleration.md) — 7713 / 7714 내비 감속 적용 비교

### 集群 / 仪表显示（2 篇，其中长期参考 1）

- [`docs/staria_ev_registration.md`](docs/staria_ev_registration.md) — Hyundai Staria EV 2026 registration
- [`docs/cluster_road_camera_map_flicker_analysis.md`](docs/cluster_road_camera_map_flicker_analysis.md) — Cluster 도로 카메라 선택 시 지도 영역 카메라 깜빡임 분석

### 启动与恢复（6 篇，其中长期参考 0）

- [`docs/system_ready_sound_20260929.md`](docs/system_ready_sound_20260929.md) — Onroad readiness sound（2026-09-29）
- [`docs/reboot_sound_20260929.md`](docs/reboot_sound_20260929.md) — Reboot notification sound（2026-09-29）
- [`docs/startup_recovery.md`](docs/startup_recovery.md) — Startup update recovery — 2026-09-28
- [`docs/onroad_initialization_timeout.md`](docs/onroad_initialization_timeout.md) — Onroad initialization grace period
- [`docs/driving_mode_recovery.md`](docs/driving_mode_recovery.md) — Automatic driving-mode recovery
- [`docs/carrot_stopping_experiment.md`](docs/carrot_stopping_experiment.md) — CAN FD 정지 제어: carrot-stopping 시험 및 carrot-wip 반영

### 车辆专属记录（16 篇，其中长期参考 0）

- [`docs/ioniq5_signal_head_trial_20261010.md`](docs/ioniq5_signal_head_trial_20261010.md) — 내부 ONNX 신호 예측 학습 1차 실험 — 2026-10-10（2026-10-10）
- [`docs/pr536_review_20261009.md`](docs/pr536_review_20261009.md) — PR #536 review and integration（2026-10-09）
- [`docs/ioniq5_1044_hotplug_20261006.md`](docs/ioniq5_1044_hotplug_20261006.md) — Ioniq 5 PE Jetson/HUD hotplug, 2026-10-06（2026-10-06）
- [`docs/ioniq5_103d_late_lead_20261005.md`](docs/ioniq5_103d_late_lead_20261005.md) — Ioniq 5 PE 103d: 전방 저속 물체 선택 지연 검토（2026-10-05）
- [`docs/id4_dm_enable_cadence_20261003.md`](docs/id4_dm_enable_cadence_20261003.md) — ID.4 DM re-enable communication fault — 2026-10-03（2026-10-03）
- [`docs/ioniq5_5d7_steering_20261002.md`](docs/ioniq5_5d7_steering_20261002.md) — Ioniq 5 PE 5d7: reduced steering authority and missed handover（2026-10-02）
- [`docs/scc_longitudinal_lead_20261001.md`](docs/scc_longitudinal_lead_20261001.md) — SCC longitudinal lead continuity (2026-10-01)（2026-10-01）
- [`docs/ioniq5_pe_cluster_warning_20260930.md`](docs/ioniq5_pe_cluster_warning_20260930.md) — Ioniq 5 PE intermittent driver-assistance cluster warning（2026-09-30）
- [`docs/id4_steering_model_comparison_20260930.md`](docs/id4_steering_model_comparison_20260930.md) — ID.4 same-road model and learned-parameter comparison（2026-09-30）
- [`docs/impact_dashcam_20260929.md`](docs/impact_dashcam_20260929.md) — Suspected-impact Dashcam transition（2026-09-29）
- [`docs/ioniq5_stock_hud_flicker_20260927.md`](docs/ioniq5_stock_hud_flicker_20260927.md) — Ioniq 5 stock HUD / cluster lead-color flicker（2026-09-27）
- [`docs/ioniq9_can_startup_20260926.md`](docs/ioniq9_can_startup_20260926.md) — Ioniq 9 startup CAN/SPI failure, 2026-09-26（2026-09-26）
- [`docs/ioniq5_acceleration_20260926.md`](docs/ioniq5_acceleration_20260926.md) — Ioniq 5 acceleration oscillation, 2026-09-26（2026-09-26）
- [`docs/carnival_stopping_path_endpoint_20260925.md`](docs/carnival_stopping_path_endpoint_20260925.md) — Carnival braking interruption from a short stopping-path endpoint（2026-09-25）
- [`docs/ev5_cluster_corner_display.md`](docs/ev5_cluster_corner_display.md) — EV5 cluster corner-object visibility (2026-09-24)
- [`docs/carrot_web_upload.md`](docs/carrot_web_upload.md) — Carrot web upload

### 构建 / 构建时间（1 篇，其中长期参考 0）

- [`docs/build_time_floor_20261005.md`](docs/build_time_floor_20261005.md) — Offline build clock floor — 2026-10-05（2026-10-05）

## 三、AGENTS.md 点名的文档

仓库记忆（`AGENTS.md`）按路径直接引用了以下文档。**改动它们或移动它们之前，先同步更新 AGENTS.md。**

- [`docs/carrot_navi_7713_7714_deceleration.md`](docs/carrot_navi_7713_7714_deceleration.md) — 7713 / 7714 내비 감속 적용 비교
- [`docs/carrot_navi_7714_branch_comparison.md`](docs/carrot_navi_7714_branch_comparison.md) — 7714 내비 감속 브랜치 비교
- [`docs/cluster_road_camera_map_flicker_analysis.md`](docs/cluster_road_camera_map_flicker_analysis.md) — Cluster 도로 카메라 선택 시 지도 영역 카메라 깜빡임 분석

## 四、元信息约定（待补）

目前只有少数文档在正文里写了日期和结论，文件名带日期后缀的才能机械识别。

建议后续给**实验记录**统一在正文开头加三行，便于不打开也能判断是否相关：

```markdown
结论: 一句话说明测出了什么（必填）
日期: 2026-10-13   车型: Ioniq 5 PE   状态: 已收敛 | 待验证 | 已被推翻
```

长期参考类文档则建议加 `状态: 有效` 并在结论有变化时更新日期。

---

*生成于分支 `friend-integ`；共 120 篇。*
