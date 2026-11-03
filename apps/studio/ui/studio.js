import { LiveDetails, drawDetails } from "/ui/live-details.js";
import * as workbench from "/ui/workbench.js";
// MoCapGate Studio — интерфейс. Чистый JS-модуль без сборки; three.js и MediaPipe Tasks грузятся лениво.
// Сервер: apps/studio/server.py (JSON-API на 127.0.0.1 с токеном сессии).

// ---------------------------------------------------------------- i18n
const STRINGS = {
  en: {
    set_gvhmr_advanced:"Advanced GVHMR paths (optional)", set_gvhmr_tip:"Install above: paths are configured automatically.", set_gvhmr_runtime:"Runtime", set_wsl_distro:"WSL distribution (blank: automatic)",
    skeleton_structure: "Skeleton structure", skeleton_tip_hint: "Terminal joints are fixed endpoints, not independently tracked.", o_mixamo_namespace: "Mixamo prefix mixamorig: (BVH / FBX)",
    setup_open: "Install components in Settings", setup_eyebrow: "FIRST LAUNCH", setup_title: "Processing models and export tools",
    setup_description: "Install FFmpeg, ffprobe and Blender. Install a recognition model separately below.",
    setup_recommended: "Install export tools", setup_preferences: "Preferences and advanced paths",
    setup_ready: "Export tools are ready. Choose a recognition model below.", setup_missing: "Still needed: ",
    rig_capture: "Capture skeleton", rig_custom: "Custom Maya rig", rig_label: "Maya character", rig_path: "Custom rig (.ma)", o_hand_stability: "Stabilize wrists and fingers", studio: "Studio", person: "Person", o_people: "Maximum people (1–8)", o_single_actor_multiview: "One person shown in several camera views", o_single_actor_multiview_hint: "Limits detection to one person; it does not combine camera views. For a split-screen clip, crop one half below. True camera fusion needs separate synchronized, calibrated videos.", o_view_crop: "View in a side-by-side clip", o_view_crop_full: "Whole frame", o_view_crop_left: "Left half only", o_view_crop_right: "Right half only", o_view_crop_hint: "Crops the selected half before body and hand recognition. It does not fuse views. The original video remains in the take.", tab_takes: "Takes", tab_camera: "Camera", tab_status: "Models & tools", tab_settings: "Settings",
    open_browser: "Open in browser", open_browser_hint: "The same app in your web browser (handy for the camera)",
    new_take: "+ Import video", no_takes: "No takes yet. Drop a video here or record one with the camera.",
    reveal_library: "Show library folder", new_title: "New take",
    new_sub: "A video of a person → animation of a skeleton (BVH / FBX) for Blender, Maya and engines.",
    drop_title: "Drop a video here", drop_hint: "mp4, mov, webm — or a result from Colab (.zip / .mocapgate.json)", preview_loading: "Video preview · available while the file uploads", preview_unavailable: "This format cannot be previewed in the browser; upload can continue.",
    take_name: "Name", backend: "How to recognize the motion",
    be_gemx: "77 joints: body, hands and face. Experimental; static camera.", be_mediapipe: "On this computer, no GPU. Body, optional hands and face. Quick to try.",
    be_colab: "Body motion in world coordinates, using a Colab GPU.",
    be_local: "Body motion on your NVIDIA GPU. Install in Models & tools.", this_pc: "this PC",
    be_multiview_title: "Calibrated multi-camera", be_multiview: "Import a session ZIP with separate synchronized static-camera videos and measured calibration.",
    multiview_zip_hint: "Choose one calibrated multi-camera session .zip", multiview_batch_hint: "Multi-camera sessions are processed one at a time.",
    options: "Options", start: "Make the animation",
    colab_title: "GVHMR in Colab — three steps",
    colab_1: "Download the notebook below. In Google Colab choose File → Upload notebook, then Runtime → T4 GPU. A Google account is enough.",
    colab_2: "Run the cells; at step 3 upload SMPLX_NEUTRAL.npz once (free sign-up at smpl-x.is.tue.mpg.de), at step 4 — your video.",
    colab_3: "Drop the downloaded *_mocapgate.zip into this take — it gets checked and exported here.",
    open_colab: "Open in Colab", download_notebook: "Download notebook (.ipynb)",
    colab_private_hint: "Download the notebook here, then use File → Upload notebook in Colab. No GitHub access needed.", delete: "Delete", cancel: "Cancel",
    waiting_colab: "Waiting for the result from Colab. Run the notebook with this video, then drop the *_mocapgate.zip here.",
    attach_hint: "Drop the Colab result (.zip or .mocapgate.json + .mp4)",
    no_video: "No video in this take — the 3D view plays on its own.",
    layer_hands: "Hands and fingers", layer_face: "Face points", layer_detected: "Body points", layer_skeleton: "Our skeleton projected back",
    three_hint: "Drag to turn; click the view, then wheel to zoom (or Ctrl/⌘ + wheel). The grid is the floor, 1 m cells. Keys: Space play, ←/→ frame, I/O range.",
    check_title: "Video and model checks", output_motion_title: "Final animation (BVH)", output_contact_frames: "contact frames", output_contact_intervals: "contact intervals", output_contact_none: "No reliable foot support was detected; foot drift cannot be measured.", output_foot_drift: "max drift during support", output_foot_drift_none: "not enough contact frames to measure", output_quality_hint: "Measures are computed from the exported BVH after motion cleanup; these are diagnostics, not ground-truth accuracy.", r_foot_skate_low_evidence: "Few foot-contact frame pairs were available; speed is shown for inspection but excluded from the score.", tune_title: "Tune and process again", reprocess: "Process again", load_title: "Computer load: GPU, video memory, RAM. Click for the performance test", o_chunk: "Process in parts (memory)", o_chunk_auto: "Auto — by free memory", o_chunk_off: "Whole video at once", o_chunk_hint: "Long videos are split into overlapping parts and stitched smoothly — fits weaker GPUs and less RAM. Auto picks the length from free video memory and RAM.", bench_title: "3. Performance test", bench_hint: "Runs GEM-X on the short demo video and measures speed, peak video memory and RAM (inside WSL — the VM memory), then suggests settings for this computer. Takes 2–10 minutes.", bench_run: "Run the test", bench_apply: "Use for new takes", o_gemx_fps: "Recognition frame rate", o_gemx_fps_30: "30 FPS (recommended — the model is trained on it)", o_gemx_fps_0: "As the video (up to 60, experimental)", o_gvhmr_hands: "Hands and fingers from", o_gvhmr_hands_auto: "Auto — GEM-X if installed", o_gvhmr_hands_gemx: "GEM-X (better wrists and fingers)", o_gvhmr_hands_mediapipe: "MediaPipe", o_gvhmr_hands_hint: "Works with “Hands and fingers” on. GVHMR keeps the body and feet; wrists and fingers come from a GEM-X pass over the same video (cached; first time adds a GEM-X run). If GEM-X fails, MediaPipe hands are used.", o_gemx_fps_hint: "The animation is exported at the source frame rate either way (Export FPS). Recognizing at 60 doubles memory and time; quality on fast moves may improve, but the model was trained at 30.", o_max_px: "Recognition resolution (long side)", o_max_px_0: "Original (needs much more memory)", o_max_px_hint: "The video is downscaled only for recognition; the overlay and export are not affected. 4K at full size often runs out of memory — 1920 is enough for people in frame; 1280 for weak PCs.", camera_capture: "From the filming camera", pin_lh: "Left hand", pin_rh: "Right hand", pin_lf: "Left foot", pin_rf: "Right foot", pe_pin: "Hold in place on In–Out (IK)", pe_pin_hint: "The hand or foot stays where it is at the In frame through In–Out (e.g. a hand on a table); the arm/leg is solved by IK. Visible after “Apply”.", pe_hand_candidate_use: "Review as hand pin", pe_hand_candidate_hint: "Candidates are based on low wrist speed. Review against the video; this is not confirmed object contact.", dl_audio: "Sound from the video (WAV)", layout: "Layout", layout_auto: "Auto", layout_side: "Video and 3D side by side", layout_big3d: "Large 3D", layout_bigvideo: "Large video", version_restore: "Restore", version_restore_confirm: "Restore the animation from {d}? The current one is saved to versions first.", version_restored: "Previous version restored", wait_reveal: "Show the video file", wait_local: "Process on this PC instead", leave_import: "The uploaded files have not become a take yet. Leave the import?", onion: "Ghost poses", onion_off: "Off", pe_title: "Pose editing and foot contacts", pe_hint: "Click a joint in 3D or pick it below. Sliders rotate it at the current frame; “Set key” keeps it, the falloff blends it into neighbouring frames. Changes show immediately; “Apply” writes them into the animation (the previous version stays in history).", pe_falloff: "Falloff, frames", pe_key: "Set key", pe_zero: "Reset sliders", pe_curves_hint: "Curves: rotation Z (blue) / X (red) / Y (green) of the joint over the take; yellow — keys; click to jump. Rows L / R: green — foot planted (added), red — foot free (removed); the rest is detected automatically.", pe_contact_l: "Left foot planted on In–Out", pe_contact_r: "Right foot planted on In–Out", pe_contact_free: "Feet free on In–Out", pe_apply: "Apply edits", pe_discard: "Discard unsaved edits", marker_add: "+ Marker", marker_hint: "Name the current frame (M); jump to markers from the list", clip_edit: "Edit the clip: mirror, speed, ease, turn", ce_mirror: "Mirror (left ↔ right)", ce_floor: "Put feet on the floor", ce_speed: "Speed ×", ce_yaw: "Turn around vertical, °", ce_scale: "Path scale (bones unchanged)", ce_ease_in: "Ease in, s", ce_ease_out: "Ease out, s", search_takes: "Search takes, tags…", select_many: "Select several for export", take_info: "Project, tags and notes", project: "Project", tags: "Tags (comma separated)", notes: "Notes", dup_run: "Process as a new take", wiz_title: "Installation, step by step", wiz_check: "1. Check the computer", wiz_check_hint: "Windows/macOS version, memory, disk, NVIDIA driver, WSL, internet access to the download servers. Problems come with a fix.", wiz_check_run: "Check the computer", wiz_install: "2. Install everything recommended", wiz_terms: "I accept the GVHMR and model terms (non-commercial use)", wiz_install_run: "Install everything recommended", wiz_install_hint: "Already installed parts are skipped. If the internet drops, press the button again — downloads resume.", wiz_try: "4. Try it", wiz_demo: "Open the demo take", wiz_report: "Support report", wiz_report_hint: "The report (system check, versions, install logs; no videos or animations) is saved to Downloads — you decide whom to send it to.", engines_title: "For game engines", eng_root_motion: "Root motion (a separate root bone carries the travel)", eng_all: "All participants in one file", char_title: "Your character", char_hint: "Upload your rigged character (.fbx, .glb, .blend): bones are matched automatically (Mixamo, UE, Unity, Rigify, CC, Daz, VRoid) and the motion is baked onto it. Facial curves go to matching ARKit shape keys.", char_upload: "Upload character", char_run: "Transfer animation", char_none: "No characters yet — upload one", char_added: "Character added", download: "Download", clip_make_loop: "Seamless loop", clip_root_motion: "Root bone (root motion)", repair_range: "Fix these frames", repair_hint: "Replace frames In–Out with smooth interpolation of their neighbours (the previous version is kept in history)", repair_confirm: "Replace frames {a}–{b} with smooth interpolation? The previous version stays in “Previous animation versions”.", o_smooth_body: "Smooth body jitter", o_smooth_hands: "Smooth finger jitter", o_smooth_hint: "0 — as recognized. Higher removes shaking; fast moves stay sharp (adaptive filter).", set_updates: "Check for new versions (anonymous request to GitHub)", update_available: "New version {v} — download", unsaved: "Unsaved changes — click Save", set_gemx_dir: "GEM-X — repository", gvhmr_this_pc: "GVHMR · this PC", profile_name: "Name", profile_scale: "Trajectory scale", profile_yaw: "Yaw (Y rotation), °", profile_map: "JSON: source → character joint", process_now: "Make the animation", open_models: "Open Models & tools", queue_start_now: "Start the queue", options_changed: "Settings changed — process again to apply them.", queued_paused: "Waiting in the processing queue. The queue is paused.", queued_waiting: "Waiting in the processing queue — it starts after the current take.", not_installed: "Not installed",
    export_title: "Export", dl_bvh: "Download BVH", make_fbx: "Make FBX (Maya, Unity, Unreal)", dl_fbx: "Download FBX",
    maya_steps_title: "Finish in Maya", maya_step_scene: "Download the Maya scene (.ma) and open it in Maya. The character and export FPS are already prepared.", maya_step_tools: "Optional: download Maya finishing tools (.py), open in Script Editor → Python and run.", maya_step_layer: "Click Create additive correction layer. Keep MoCapGate_Corrections selected when keying; save edits with Save As.", maya_steps_limit: "These tools edit joints; IK/FK controllers are not included. FBX contains the capture skeleton; the full character is in .ma.", dl_maya_tools: "Maya finishing tools (.py)", creating_animation: "Creating 3D animation…", dl_ma: "Download Maya scene (.ma)", open_blender: "Open in Blender", open_maya: "Open character in Maya", reveal: "Show in folder",
    export_hint: "Blender: File → Import → Motion Capture (.bvh), Scale 0.01. Maya: open the native .ma, or use “Open character in Maya” with the selected rig.",
    cam_off: "The camera is off.", cam_start: "Turn on the camera", cam_device: "Camera", cam_res: "Resolution",
    cam_countdown: "Countdown, s", live_check: "Live check: skeleton and hints", rec_start: "● Record", rec_stop: "■ Stop",
    rec_use: "Make a take from it", rec_again: "Record again",
    rec_backend_hint: "Colab: the take waits for the notebook result. GEM-X and GVHMR on this PC process right away.", rec_model: "Recognize with",
    tips_title: "How to film for good mocap",
    tip_1: "The whole body in frame, head to feet, with a little room around.",
    tip_2: "Camera at waist height, still (a tripod or a shelf).",
    tip_3: "Even light, no strong backlight; clothes that contrast with the background.",
    tip_4: "Start and end in a T-pose or standing still for a second.",
    tip_5: "Keep people separated and visible; avoid clothes that hide knees and elbows.",
    status_title: "Models & tools", status_sub: "What is found on this computer, what is missing and how to add it.",
    refresh: "Check again", settings_title: "Settings", set_lang: "Language", lang_auto: "As the system",
    set_library: "Takes folder", set_backend: "Recognition by default",
    set_smplx: "SMPL-X model (exact bone lengths for GVHMR)", set_blender: "Blender (if not found by itself)",
    set_maya: "Maya (optional)", set_gvhmr_dir: "GVHMR folder (NVIDIA GPU)", set_gvhmr_py: "Python of the GVHMR environment",
    save: "Save", saved: "Saved", settings_file: "Settings file: ",
    // options
    o_pose_model: "MediaPipe model", o_model_lite: "lite — fast", o_model_full: "full", o_model_heavy: "heavy — most accurate",
    o_smoothing: "Smoothing", o_root: "Root motion", o_root_image: "Move as in the video", o_root_inplace: "In place",
    o_surface: "Full SMPL-X avatar (local model required)", o_view_mode: "3D view", version_history: "Previous animation versions", clip_in: "In frame", clip_out: "Out frame", mark_in: "Set In", mark_out: "Set Out", clip_loop: "Loop range", clip_reset: "Full take", clip_inplace: "Clip: in place (keep jumps)", clip_fbx: "Include FBX (Blender)", export_clip: "Export selected range", dl_clip: "Download clip archive", camera_view: "Camera view", camera_free: "Orbit", camera_front: "Front", camera_back: "Back", camera_side: "Side", camera_follow: "Follow character", o_view_character: "Man_Rig character", o_view_surface: "Capture body", o_view_bones: "Bones", o_view_both: "Body + bones", o_hands: "Hand fingers (BVH / FBX)", o_face: "Full face and expressions", o_detail_hint: "SMPL-X displays a neutral avatar with approximate facial expression fitting. Expressions export as 52 ARKit curves: CSV, a FaceExpressions node in Maya and blend shapes in FBX. Feet: heel and toe only; individual toes are not detected.", o_details: "Hands / face data (JSON)", o_face_curves: "Facial expressions (52 curves, CSV)", o_foot_lock: "Pin the feet to the floor", o_focal: "Camera focal length, mm (35 mm eq.)",
    o_focal_hint: "0 — find automatically. Phone main camera ≈ 26, ultra-wide ≈ 13, 2× ≈ 48",
    o_space: "GVHMR space", o_space_global: "World (with the path)", o_space_incam: "Relative to the camera",
    o_gemx_quality: "GEM-X model mode", o_gemx_q_fast: "Fast (ONNX)", o_gemx_q_accurate: "Accurate (PyTorch + foot contacts)", o_gemx_q_max: "Maximum (DDIM, 50 steps)",
    o_gemx_quality_hint: "Accurate fixes feet on the ground with GEM-X post-processing; Maximum samples the motion 50 times — several times slower.",
    o_gemx_f: "Camera focal length, mm (0 — GEM-X estimate)", o_gemx_f_hint: "35 mm equivalent: phone main ≈ 26, ultra-wide ≈ 13, 2× ≈ 48. Affects distance and height.",
    o_gemx_score: "Person detection confidence", o_gemx_score_hint: "Lower — finds small or partly hidden people (and more false ones); higher — only clear people.",
    o_gemx_min: "Shortest participant, s", o_gemx_min_hint: "People seen for less time are ignored (passers-by, flicker at the frame edge).",
    o_gemx_memory: "Remember a lost person, frames", o_gemx_memory_hint: "How long a person may be hidden and keep the same ID (30 ≈ 1 s).",
    o_fps: "Export frame rate", o_static: "The camera stands still (GVHMR)", o_gvhmr_f: "Focal for GVHMR, mm (0 — auto)",
    // statuses
    st_new: "new", st_processing: "processing", st_done: "done", st_error: "error", st_waiting: "waiting for Colab",
    frames: "frames", focal: "focal", uploading: "Uploading", uploaded: "uploaded",
    pick_files: "Pick a video or a result first", need_mediapipe: "Install MediaPipe in Models & tools first",
    need_local: "Install GVHMR in Models & tools first (NVIDIA GPU)", colab_video_hint: "The video is kept in the take; send the same video to Colab.",
    started: "Processing started", saved_to: "Saved: ", deleted: "Take deleted, freed ", trash_empty: "Delete old trash", trash_done: "Old trash deleted, freed ",
    confirm_delete: "Delete this take for good? The video, recognition results, BVH/FBX/Maya files and saved versions will be removed from this computer. This cannot be undone.",
    confirm_trash: "Delete takes left in .trash by earlier versions? They cannot be restored.",
    fbx_done: "FBX is ready", processing_done: "Done",
    verdict_good: "A good take — ready to use.", verdict_warn: "Usable, but look at the notes below.",
    verdict_bad: "A weak take — better film again following the advice below.", quality_scope: "This is a model-derived consistency check, not ground-truth accuracy. Independent accuracy requires reference motion or manual annotations.",
    r_found: "Person found in frames", r_found_adv: "Sometimes the person is lost — check the light and that nothing covers them.",
    r_gap: "Longest gap", r_gap_adv: "Gaps are filled with the neighbouring frames — motion freezes there.",
    r_out_of_frame: "Out of frame", r_out_of_frame_adv: "Keep the whole body in frame — step back or move the camera away.",
    r_size: "Size in frame", r_size_adv: "The person is small — come closer or film in a higher resolution.",
    r_vis_arms: "Arms visible", r_vis_arms_adv: "Arms are often hidden or blurred — film from the front, brighter light, contrasting sleeves.",
    r_vis_legs: "Legs visible", r_vis_legs_adv: "Legs are often hidden — the whole body in frame, contrasting trousers.",
    r_vis_head: "Head visible", r_vis_head_adv: "The face is often turned away or out of frame.",
    r_hand_left_coverage: "Left hand detected", r_hand_right_coverage: "Right hand detected",
    r_hand_left_coverage_adv: "Detection coverage only; occlusion can hide a hand. This does not measure finger-pose accuracy.",
    r_hand_right_coverage_adv: "Detection coverage only; occlusion can hide a hand. This does not measure finger-pose accuracy.",
    r_jitter: "Jitter", r_jitter_adv: "Raise the smoothing, or film with more light (less motion blur).",
    r_foot_skate: "Foot sliding", r_foot_skate_adv: "Turn on pinning the feet; one camera always leaves a little sliding — GVHMR is cleaner.",
    r_upper_body: "Upper body only", r_upper_body_adv: "The legs are not in frame, so they are kept straight and the feet are not pinned. For full-body mocap, film head to feet.",
    r_reprojection: "Skeleton matches the video", r_reprojection_adv: "The skeleton drifts from the video — check the focal length or try GVHMR.",
    bones_model: "bones from the SMPL-X model", bones_average: "average bone lengths", bones_soma: "SOMA skeleton (GEM-X)", camera_at: "camera {h} m above the floor",
    // live hints
    h_loading: "Loading the live check…", h_none: "No person in frame", h_edges: "Keep the whole body in frame (head, hands, feet)",
    h_far: "Too far — come closer", h_near: "Too close — step back", h_dark: "Too dark — add light",
    h_legs: "Legs are poorly visible", h_ok: "Everything is visible — ready to record", h_failed: "Live check unavailable: ",
    cam_denied: "No access to the camera: ", cam_none: "No camera found",
    // status cards
    s_python: "Python", s_gpu: "Graphics / compute", s_mediapipe: "MediaPipe — pose on this computer",
    s_mediapipe_desc: "Recognizes 33 body points in each frame on the CPU. Apache-2.0, ~1 GB, installed in its own folder.",
    s_install: "Install", s_installed: "Installed", s_models: "Models: ", s_get_model: "Download model",
    s_gvhmr: "GVHMR · body and trajectory", s_gvhmr_colab: "In Google Colab (free GPU): no install on this computer.",
    s_gvhmr_local: "On this computer: needs an NVIDIA GPU and GVHMR installed by its guide; then set its folder in Settings.",
    s_gvhmr_ready: "GVHMR on this computer is ready", s_gvhmr_missing: "Missing for local GVHMR: ",
    s_smplx: "SMPL-X body model", s_smplx_desc: "Upload SMPLX_NEUTRAL.npz once. It is placed in the correct folder automatically. Free sign-up, non-commercial licence.",
    s_smplx_upload: "Upload SMPLX_NEUTRAL.npz or the .zip from the site", s_smplx_site: "Get it (smpl-x.is.tue.mpg.de)",
    s_blender: "Blender", s_blender_desc: "Makes FBX and opens takes with the animation.", s_maya: "Maya",
    s_maya_desc: "Opens the prepared Maya scene with the character and export frame rate.",
    s_ffmpeg: "ffmpeg", s_ffmpeg_desc: "Turns camera recordings into mp4 with a steady frame rate; needed for local GVHMR.",
    s_uv: "uv", s_uv_desc: "Installs MediaPipe with the right Python version.", s_found: "Found: ", s_not_found: "Not found",
    s_download: "Download", s_install_guide: "How to install", missing_folder: "folder", missing_checkpoints: "weights",
    missing_smplx: "SMPL-X", missing_python: "python", missing_cuda: "NVIDIA GPU (CUDA)",
  },
  ru: {
    set_gvhmr_advanced:"Ручные пути GVHMR (необязательно)", set_gvhmr_tip:"Установите выше: пути настроятся автоматически.", set_gvhmr_runtime:"Окружение", set_wsl_distro:"Дистрибутив WSL (пусто: автоматически)",
    skeleton_structure: "Структура скелета", skeleton_tip_hint: "Окончания цепочек — фиксированные точки, без отдельного распознавания.", o_mixamo_namespace: "Префикс Mixamo mixamorig: (BVH / FBX)",
    setup_open: "Установить компоненты в настройках", setup_eyebrow: "ПЕРВЫЙ ЗАПУСК", setup_title: "Модели обработки и инструменты экспорта",
    setup_description: "Установите инструменты видео и экспорта. Модель распознавания выберите ниже.",
    setup_recommended: "Установить инструменты экспорта", setup_preferences: "Предпочтения и дополнительные пути",
    setup_ready: "Инструменты экспорта готовы. Выберите модель ниже.", setup_missing: "Осталось установить: ",
    rig_capture: "Скелет захвата", rig_custom: "Свой риг Maya", rig_label: "Персонаж Maya", rig_path: "Пользовательский риг (.ma)", o_hand_stability: "Стабилизация запястий и пальцев", studio: "Studio", person: "Участник", o_people: "Максимум людей (1–8)", o_single_actor_multiview: "Один человек показан с нескольких камер", o_single_actor_multiview_hint: "Ограничивает распознавание одним человеком, но не совмещает ракурсы. Для составного видео выберите половину ниже. Для объединения камер нужны отдельные синхронизированные и откалиброванные записи.", o_view_crop: "Ракурс в составном видео", o_view_crop_full: "Весь кадр", o_view_crop_left: "Только левая половина", o_view_crop_right: "Только правая половина", o_view_crop_hint: "Выбранная половина вырезается перед распознаванием тела и кистей. Ракурсы не объединяются; исходное видео сохраняется в дубле.", tab_takes: "Дубли", tab_camera: "Камера", tab_status: "Модели и инструменты", tab_settings: "Настройки",
    open_browser: "Открыть в браузере", open_browser_hint: "То же приложение в браузере (удобно для камеры)",
    new_take: "+ Импорт видео", no_takes: "Дублей пока нет. Перетащите видео сюда или запишите с камеры.",
    reveal_library: "Папка библиотеки", new_title: "Новый дубль",
    new_sub: "Видео с человеком → анимация скелета (BVH / FBX) для Blender, Maya и движков.",
    drop_title: "Перетащите видео сюда", drop_hint: "mp4, mov, webm — или результат из Colab (.zip / .mocapgate.json)", preview_loading: "Предпросмотр видео · доступен, пока файл загружается", preview_unavailable: "Браузер не показывает этот формат, но загрузка продолжится.",
    take_name: "Название", backend: "Чем распознавать движение",
    be_gemx: "77 суставов: тело, кисти и лицо. Экспериментально; статичная камера.", be_mediapipe: "На этом компьютере, без видеокарты. Тело, кисти и лицо по выбору. Быстро попробовать.",
    be_colab: "Движение тела в мировых координатах, расчёт на GPU в Colab.",
    be_local: "Движение тела на вашей NVIDIA. Установка в «Модели и инструменты».", this_pc: "этот ПК",
    be_multiview_title: "Калиброванные камеры", be_multiview: "ZIP-сессия: отдельные синхронизированные видео неподвижных камер и измеренная калибровка.",
    multiview_zip_hint: "Выберите один .zip калиброванной многокамерной сессии", multiview_batch_hint: "Многокамерные сессии обрабатываются по одной.",
    options: "Настройки", start: "Сделать анимацию",
    colab_title: "GVHMR в Colab — три шага",
    colab_1: "Скачайте ноутбук кнопкой ниже. В Google Colab: «Файл → Загрузить блокнот», затем «Среда выполнения → T4 GPU». Достаточно аккаунта Google.",
    colab_2: "Запустите ячейки; на шаге 3 один раз загрузите SMPLX_NEUTRAL.npz (бесплатная регистрация на smpl-x.is.tue.mpg.de), на шаге 4 — ваше видео.",
    colab_3: "Перетащите скачанный *_mocapgate.zip в этот дубль — здесь он проверяется и экспортируется.",
    open_colab: "Открыть в Colab", download_notebook: "Скачать ноутбук (.ipynb)",
    colab_private_hint: "Скачайте ноутбук здесь, затем в Colab: «Файл → Загрузить блокнот». Доступ к GitHub не требуется.", delete: "Удалить", cancel: "Отменить",
    waiting_colab: "Ждём результат из Colab. Запустите ноутбук с этим видео и перетащите сюда *_mocapgate.zip.",
    attach_hint: "Перетащите результат Colab (.zip или .mocapgate.json + .mp4)",
    no_video: "В дубле нет видео — 3D-вид проигрывается сам.",
    layer_hands: "Кисти и пальцы", layer_face: "Точки лица", layer_detected: "Точки тела", layer_skeleton: "Наш скелет, спроецированный обратно",
    three_hint: "Тяните — поворот; щёлкните по виду, затем колесо — масштаб (или Ctrl/⌘ + колесо). Сетка — пол, клетка 1 м. Клавиши: пробел — пуск, ←/→ — кадр, I/O — участок.",
    check_title: "Проверки видео и модели", output_motion_title: "Итоговая анимация (BVH)", output_contact_frames: "кадров опоры", output_contact_intervals: "интервалов опоры", output_contact_none: "Надёжные участки опоры стоп не найдены; скольжение измерить нельзя.", output_foot_drift: "макс. сдвиг в опоре", output_foot_drift_none: "недостаточно кадров контакта для измерения", output_quality_hint: "Показатели вычислены по экспортированному BVH после доводки движения; это диагностика, а не точность по эталону.", r_foot_skate_low_evidence: "Для оценки доступно мало пар кадров с опорой; скорость показана для просмотра, но не влияет на балл.", tune_title: "Настроить и обработать заново", reprocess: "Обработать заново", load_title: "Загрузка компьютера: видеокарта, видеопамять, ОЗУ. Щелчок — тест производительности", o_chunk: "Обработка частями (память)", o_chunk_auto: "Авто — по свободной памяти", o_chunk_off: "Всё видео сразу", o_chunk_hint: "Длинное видео делится на части с перекрытием и плавно склеивается — помещается в слабую видеокарту и меньшую ОЗУ. «Авто» выбирает длину по свободной видеопамяти и ОЗУ.", bench_title: "3. Тест производительности", bench_hint: "Прогоняет GEM-X на коротком демо-видео и замеряет скорость, пик видеопамяти и ОЗУ (в WSL — память виртуальной машины), затем предлагает настройки для этого компьютера. Занимает 2–10 минут.", bench_run: "Запустить тест", bench_apply: "Применить для новых дублей", o_gemx_fps: "Частота распознавания", o_gemx_fps_30: "30 FPS (рекомендовано — на ней обучена модель)", o_gemx_fps_0: "Как у видео (до 60, экспериментально)", o_gvhmr_hands: "Кисти и пальцы — откуда", o_gvhmr_hands_auto: "Авто — GEM-X, если установлен", o_gvhmr_hands_gemx: "GEM-X (точнее запястья и пальцы)", o_gvhmr_hands_mediapipe: "MediaPipe", o_gvhmr_hands_hint: "Работает при включённых «Кистях и пальцах». Тело и стопы — от GVHMR, запястья и пальцы — из прохода GEM-X по тому же видео (кэшируется; в первый раз добавляет время GEM-X). Если GEM-X не сработал — кисти MediaPipe.", o_gemx_fps_hint: "Анимация в любом случае выгружается с частотой исходного видео («FPS экспорта»). Распознавание на 60 — вдвое больше памяти и времени; быстрые движения могут стать точнее, но модель обучена на 30.", o_max_px: "Разрешение для распознавания (длинная сторона)", o_max_px_0: "Исходное (нужно намного больше памяти)", o_max_px_hint: "Видео уменьшается только для распознавания — наложение и экспорт не меняются. 4K в исходном размере часто не помещается в память; 1920 хватает для людей в кадре, 1280 — для слабых ПК.", camera_capture: "Из камеры съёмки", pin_lh: "Левая кисть", pin_rh: "Правая кисть", pin_lf: "Левая стопа", pin_rf: "Правая стопа", pe_pin: "Удерживать на месте на In–Out (IK)", pe_pin_hint: "Кисть или стопа остаётся там, где была на кадре In, весь участок In–Out (например, рука на столе); рука/нога решается IK. Видно после «Применить».", pe_hand_candidate_use: "Проверить как закрепление кисти", pe_hand_candidate_hint: "Подсказки основаны на низкой скорости кисти. Сверьте с видео: касание предмета не подтверждено.", dl_audio: "Звук из видео (WAV)", layout: "Раскладка", layout_auto: "Авто", layout_side: "Видео и 3D рядом", layout_big3d: "Крупный 3D", layout_bigvideo: "Крупное видео", version_restore: "Вернуть", version_restore_confirm: "Вернуть анимацию от {d}? Текущая сначала сохранится в версиях.", version_restored: "Прежняя версия возвращена", wait_reveal: "Показать файл видео", wait_local: "Обработать на этом ПК", leave_import: "Загруженные файлы ещё не стали дублем. Уйти из импорта?", onion: "Призрачные позы", onion_off: "Нет", pe_title: "Правка позы и опоры стоп", pe_hint: "Щёлкните сустав в 3D или выберите ниже. Ползунки поворачивают его на текущем кадре; «Поставить ключ» сохраняет, спад плавно распространяет правку на соседние кадры. Видно сразу; «Применить» записывает в анимацию (прежняя версия остаётся в истории).", pe_falloff: "Спад, кадров", pe_key: "Поставить ключ", pe_zero: "Сбросить ползунки", pe_curves_hint: "Кривые: поворот Z (синий) / X (красный) / Y (зелёный) сустава по дублю; жёлтые — ключи; щелчок — переход. Строки Л / П: зелёный — стопа стоит (добавлено), красный — стопа свободна (убрано); остальное определяется автоматически.", pe_contact_l: "Левая стопа стоит на In–Out", pe_contact_r: "Правая стопа стоит на In–Out", pe_contact_free: "Стопы свободны на In–Out", pe_apply: "Применить правки", pe_discard: "Отменить несохранённые правки", marker_add: "+ Маркер", marker_hint: "Назвать текущий кадр (M); переход к маркерам — из списка", clip_edit: "Правка фрагмента: зеркало, скорость, вход/выход, поворот", ce_mirror: "Зеркально (левое ↔ правое)", ce_floor: "Поставить стопы на пол", ce_speed: "Скорость ×", ce_yaw: "Поворот вокруг вертикали, °", ce_scale: "Масштаб пути (кости не меняются)", ce_ease_in: "Плавный вход, с", ce_ease_out: "Плавный выход, с", search_takes: "Поиск дублей, тегов…", select_many: "Выбрать несколько для экспорта", take_info: "Проект, теги и заметки", project: "Проект", tags: "Теги (через запятую)", notes: "Заметки", dup_run: "Обработать новым дублем", wiz_title: "Установка шаг за шагом", wiz_check: "1. Проверить компьютер", wiz_check_hint: "Версия Windows/macOS, память, диск, драйвер NVIDIA, WSL, доступ к серверам загрузки. Для каждой проблемы — как исправить.", wiz_check_run: "Проверить компьютер", wiz_install: "2. Установить всё рекомендуемое", wiz_terms: "Принимаю условия GVHMR и моделей (некоммерческое использование)", wiz_install_run: "Установить всё рекомендуемое", wiz_install_hint: "Уже установленное пропускается. Если пропал интернет — нажмите кнопку снова, загрузка продолжится.", wiz_try: "4. Попробовать", wiz_demo: "Открыть демо-дубль", wiz_report: "Отчёт для поддержки", wiz_report_hint: "Отчёт (проверка компьютера, версии, журналы установки; без видео и анимаций) сохраняется в «Загрузки» — вы сами решаете, кому его отправить.", engines_title: "Для игровых движков", eng_root_motion: "Root motion (перемещение несёт отдельная корневая кость)", eng_all: "Все участники одним файлом", char_title: "Свой персонаж", char_hint: "Загрузите своего персонажа со скелетом (.fbx, .glb, .blend): кости сопоставятся сами (Mixamo, UE, Unity, Rigify, CC, Daz, VRoid), движение запечётся на него. Мимика — на shape keys с именами ARKit.", char_upload: "Загрузить персонажа", char_run: "Перенести анимацию", char_none: "Персонажей пока нет — загрузите", char_added: "Персонаж добавлен", download: "Скачать", clip_make_loop: "Бесшовный цикл", clip_root_motion: "Корневая кость (root motion)", repair_range: "Исправить эти кадры", repair_hint: "Заменить кадры участка In–Out плавной интерполяцией соседних (прежняя версия сохранится в истории)", repair_confirm: "Заменить кадры {a}–{b} плавной интерполяцией? Прежняя версия останется в «Предыдущих версиях анимации».", o_smooth_body: "Сгладить дрожание тела", o_smooth_hands: "Сгладить дрожание пальцев", o_smooth_hint: "0 — как распознано. Больше — меньше дрожания; быстрые движения остаются чёткими (адаптивный фильтр).", set_updates: "Проверять новые версии (анонимный запрос к GitHub)", update_available: "Новая версия {v} — скачать", unsaved: "Есть несохранённые изменения — нажмите «Сохранить»", set_gemx_dir: "GEM-X — папка репозитория", gvhmr_this_pc: "GVHMR · этот ПК", profile_name: "Название", profile_scale: "Масштаб траектории", profile_yaw: "Поворот по Y, °", profile_map: "JSON: источник → сустав персонажа", process_now: "Сделать анимацию", open_models: "Открыть «Модели и инструменты»", queue_start_now: "Запустить очередь", options_changed: "Настройки изменены — обработайте заново, чтобы применить.", queued_paused: "Дубль ждёт в очереди обработки. Очередь на паузе.", queued_waiting: "Дубль ждёт в очереди — начнётся после текущего.", not_installed: "Не установлено",
    export_title: "Экспорт", dl_bvh: "Скачать BVH", make_fbx: "Сделать FBX (Maya, Unity, Unreal)", dl_fbx: "Скачать FBX",
    maya_steps_title: "Доводка в Maya", maya_step_scene: "Скачайте сцену Maya (.ma) и откройте её в Maya. Персонаж и FPS экспорта уже настроены. Если Maya установлена, можно нажать «Открыть персонажа в Maya».", maya_step_tools: "Для ручных поправок скачайте «Инструменты правок Maya (.py)». Откройте файл в Script Editor → Python и выполните его.", maya_step_layer: "Нажмите Create additive correction layer. При постановке ключей держите MoCapGate_Corrections выбранным. Сохраните правки через Save As в отдельную сцену.", maya_steps_limit: "Правки выполняются через суставы; IK/FK-контроллеры пока не входят. FBX содержит скелет распознавания, полный персонаж — в .ma.", dl_maya_tools: "Инструменты правок Maya (.py)", creating_animation: "Создаётся 3D-анимация…", dl_ma: "Скачать сцену Maya (.ma)", open_blender: "Открыть в Blender", open_maya: "Открыть персонажа в Maya", reveal: "Показать в папке",
    export_hint: "Blender: File → Import → Motion Capture (.bvh), Scale 0.01. Maya: откройте .ma или нажмите «Открыть персонажа в Maya» с выбранным ригом.",
    cam_off: "Камера выключена.", cam_start: "Включить камеру", cam_device: "Камера", cam_res: "Разрешение",
    cam_countdown: "Обратный отсчёт, с", live_check: "Живая проверка: скелет и подсказки", rec_start: "● Записать", rec_stop: "■ Стоп",
    rec_use: "Сделать дубль", rec_again: "Переснять",
    rec_backend_hint: "Colab: дубль ждёт результат из тетрадки. GEM-X и GVHMR на этом ПК обрабатывают сразу.", rec_model: "Распознать моделью",
    tips_title: "Как снимать для хорошего мокапа",
    tip_1: "Всё тело в кадре, от головы до стоп, с небольшим запасом.",
    tip_2: "Камера на уровне пояса и неподвижна (штатив или полка).",
    tip_3: "Ровный свет, без сильной засветки сзади; одежда контрастирует с фоном.",
    tip_4: "Начинайте и заканчивайте в T-позе или стоя неподвижно секунду.",
    tip_5: "Люди должны быть видны раздельно; одежда не должна скрывать колени и локти.",
    status_title: "Модели и инструменты", status_sub: "Что найдено на компьютере, чего не хватает и как добавить.",
    refresh: "Проверить заново", settings_title: "Настройки", set_lang: "Язык", lang_auto: "Как в системе",
    set_library: "Папка дублей", set_backend: "Распознавание по умолчанию",
    set_smplx: "Модель SMPL-X (точные длины костей для GVHMR)", set_blender: "Blender (если не нашёлся сам)",
    set_maya: "Maya (необязательно)", set_gvhmr_dir: "Папка GVHMR (видеокарта NVIDIA)", set_gvhmr_py: "Python окружения GVHMR",
    save: "Сохранить", saved: "Сохранено", settings_file: "Файл настроек: ",
    o_pose_model: "Модель MediaPipe", o_model_lite: "lite — быстрая", o_model_full: "full", o_model_heavy: "heavy — точнее всех",
    o_smoothing: "Сглаживание", o_root: "Движение корня", o_root_image: "Перемещаться как на видео", o_root_inplace: "На месте",
    o_surface: "Полная модель SMPL-X (нужна локальная модель)", o_view_mode: "Вид 3D", version_history: "Предыдущие версии анимации", clip_in: "Первый кадр", clip_out: "Последний кадр", mark_in: "Начало здесь", mark_out: "Конец здесь", clip_loop: "Цикл участка", clip_reset: "Весь дубль", clip_inplace: "Фрагмент на месте (сохранить прыжки)", clip_fbx: "Добавить FBX (Blender)", export_clip: "Экспорт выбранного участка", dl_clip: "Скачать архив фрагмента", camera_view: "Вид камеры", camera_free: "Свободный", camera_front: "Спереди", camera_back: "Сзади", camera_side: "Сбоку", camera_follow: "Камера следует за персонажем", o_view_character: "Персонаж Man_Rig", o_view_surface: "Тело распознавания", o_view_bones: "Кости", o_view_both: "Тело + кости", o_hands: "Пальцы рук (BVH / FBX)", o_face: "Полное лицо и мимика", o_detail_hint: "SMPL-X показывает нейтральный аватар с приблизительной мимикой. Мимика экспортируется 52 кривыми ARKit: CSV, узел FaceExpressions в Maya и blend shapes в FBX. Стопы: пятка и носок; отдельные пальцы ног не распознаются.", o_details: "Кисти / лицо (JSON)", o_face_curves: "Мимика (52 кривые, CSV)", o_foot_lock: "Фиксировать стопы на полу", o_focal: "Фокус камеры, мм (35-мм экв.)",
    o_focal_hint: "0 — подобрать автоматически. Основная камера телефона ≈ 26, широкая ≈ 13, 2× ≈ 48",
    o_space: "Пространство GVHMR", o_space_global: "Мир (с траекторией)", o_space_incam: "Относительно камеры",
    o_gemx_quality: "Режим модели GEM-X", o_gemx_q_fast: "Быстро (ONNX)", o_gemx_q_accurate: "Точно (PyTorch + контакты стоп)", o_gemx_q_max: "Максимум (DDIM, 50 шагов)",
    o_gemx_quality_hint: "«Точно» прижимает стопы к полу постобработкой GEM-X; «Максимум» уточняет движение за 50 шагов — в разы дольше.",
    o_gemx_f: "Фокус камеры, мм (0 — оценка GEM-X)", o_gemx_f_hint: "35-мм экв.: основная камера телефона ≈ 26, широкая ≈ 13, 2× ≈ 48. Влияет на расстояние и высоту.",
    o_gemx_score: "Уверенность обнаружения людей", o_gemx_score_hint: "Ниже — находит мелких и частично закрытых (и больше ложных); выше — только явно видимых.",
    o_gemx_min: "Минимальная длительность участника, с", o_gemx_min_hint: "Кто был в кадре меньше — не участник (прохожие, мелькание у края кадра).",
    o_gemx_memory: "Помнить потерянного человека, кадров", o_gemx_memory_hint: "Сколько человек может быть закрыт и сохранить свой ID (30 ≈ 1 с).",
    o_fps: "FPS экспорта", o_static: "Камера неподвижна (GVHMR)", o_gvhmr_f: "Фокус для GVHMR, мм (0 — авто)",
    st_new: "новый", st_processing: "обработка", st_done: "готов", st_error: "ошибка", st_waiting: "ждёт Colab",
    frames: "кадров", focal: "фокус", uploading: "Загрузка", uploaded: "загружено",
    pick_files: "Сначала выберите видео или результат", need_mediapipe: "Сначала установите MediaPipe в «Модели и инструменты»",
    need_local: "Установите GVHMR в «Модели и инструменты» (NVIDIA)", colab_video_hint: "Видео сохранено в дубле; это же видео загрузите в Colab.",
    started: "Обработка запущена", saved_to: "Сохранено: ", deleted: "Дубль удалён, освобождено ", trash_empty: "Удалить старую корзину", trash_done: "Старая корзина удалена, освобождено ",
    confirm_delete: "Удалить дубль насовсем? С компьютера будут удалены видео, результаты распознавания, BVH/FBX/Maya и сохранённые версии. Отменить нельзя.",
    confirm_trash: "Удалить дубли, оставшиеся в .trash от прежних версий? Восстановить их будет нельзя.",
    fbx_done: "FBX готов", processing_done: "Готово",
    verdict_good: "Хороший дубль — можно в работу.", verdict_warn: "Годится, но посмотрите замечания ниже.",
    verdict_bad: "Слабый дубль — лучше переснять по советам ниже.", quality_scope: "Это внутренняя проверка согласованности модели, а не измерение точности по эталону. Для независимой оценки нужны эталонная запись движения или ручная разметка.",
    r_found: "Человек найден в кадрах", r_found_adv: "Иногда человек теряется — проверьте свет и чтобы его ничего не закрывало.",
    r_gap: "Самый долгий пропуск", r_gap_adv: "Пропуски заполнены соседними кадрами — там движение «замирает».",
    r_out_of_frame: "Выход из кадра", r_out_of_frame_adv: "Держите всё тело в кадре — отойдите или отодвиньте камеру.",
    r_size: "Размер в кадре", r_size_adv: "Человек мелко — подойдите ближе или снимайте в большем разрешении.",
    r_vis_arms: "Видимость рук", r_vis_arms_adv: "Руки часто закрыты или смазаны — снимайте спереди, свет ярче, рукава контрастнее.",
    r_vis_legs: "Видимость ног", r_vis_legs_adv: "Ноги часто не видны — всё тело в кадре, контрастные брюки.",
    r_vis_head: "Видимость головы", r_vis_head_adv: "Лицо часто отвёрнуто или вне кадра.",
    r_hand_left_coverage: "Найдена левая кисть", r_hand_right_coverage: "Найдена правая кисть",
    r_hand_left_coverage_adv: "Доля кадров с обнаружением, не точность пальцев; закрытая кисть может не определиться.",
    r_hand_right_coverage_adv: "Доля кадров с обнаружением, не точность пальцев; закрытая кисть может не определиться.",
    r_jitter: "Дрожание", r_jitter_adv: "Увеличьте сглаживание или снимайте при большем свете (меньше смаза).",
    r_foot_skate: "Проскальзывание стоп", r_foot_skate_adv: "Включите фиксацию стоп; с одной камеры немного скольжения остаётся всегда — у GVHMR чище.",
    r_upper_body: "Только верх тела", r_upper_body_adv: "Ноги не в кадре — они выставлены прямо, стопы не фиксируются. Для мокапа всего тела снимайте от головы до стоп.",
    r_reprojection: "Совпадение скелета с видео", r_reprojection_adv: "Скелет расходится с видео — проверьте фокус камеры или попробуйте GVHMR.",
    bones_model: "кости по модели SMPL-X", bones_average: "усреднённые длины костей", bones_soma: "скелет SOMA (GEM-X)", camera_at: "камера на высоте {h} м над полом",
    h_loading: "Загружаю живую проверку…", h_none: "Человека нет в кадре", h_edges: "Всё тело должно быть в кадре (голова, кисти, стопы)",
    h_far: "Далеко — подойдите ближе", h_near: "Слишком близко — отойдите", h_dark: "Темно — добавьте света",
    h_legs: "Ноги плохо видны", h_ok: "Всё видно — можно записывать", h_failed: "Живая проверка недоступна: ",
    cam_denied: "Нет доступа к камере: ", cam_none: "Камера не найдена",
    s_python: "Python", s_gpu: "Графика / вычисления", s_mediapipe: "MediaPipe — поза на этом компьютере",
    s_mediapipe_desc: "Находит 33 точки тела в каждом кадре на процессоре. Apache-2.0, ~1 ГБ, ставится в свою папку.",
    s_install: "Установить", s_installed: "Установлено", s_models: "Модели: ", s_get_model: "Скачать модель",
    s_gvhmr: "GVHMR · тело и траектория", s_gvhmr_colab: "В Google Colab (бесплатный GPU): ничего не ставится на компьютер.",
    s_gvhmr_local: "На этом компьютере: нужна видеокарта NVIDIA и GVHMR по его инструкции; затем укажите папку в «Настройках».",
    s_gvhmr_ready: "GVHMR на этом компьютере готов", s_gvhmr_missing: "Для локального GVHMR не хватает: ",
    s_smplx: "Модель тела SMPL-X", s_smplx_desc: "Один раз загрузите SMPLX_NEUTRAL.npz — программа разместит модель правильно. Бесплатная регистрация, некоммерческая лицензия.",
    s_smplx_upload: "Загрузить SMPLX_NEUTRAL.npz или .zip с сайта", s_smplx_site: "Где взять (smpl-x.is.tue.mpg.de)",
    s_blender: "Blender", s_blender_desc: "Делает FBX и открывает дубли с анимацией.", s_maya: "Maya",
    s_maya_desc: "Открывает подготовленную сцену Maya с персонажем и частотой кадров экспорта.",
    s_ffmpeg: "ffmpeg", s_ffmpeg_desc: "Превращает записи с камеры в mp4 с ровной частотой; нужен для локального GVHMR.",
    s_uv: "uv", s_uv_desc: "Ставит MediaPipe с подходящей версией Python.", s_found: "Найден: ", s_not_found: "Не найден",
    s_download: "Скачать", s_install_guide: "Как установить", missing_folder: "папка", missing_checkpoints: "веса",
    missing_smplx: "SMPL-X", missing_python: "python", missing_cuda: "видеокарта NVIDIA (CUDA)",
  },
};
let lang = "";
const t = (k) => STRINGS[lang]?.[k] ?? STRINGS.en[k] ?? k;
const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else if (v !== undefined && v !== null) e.setAttribute(k, v);
  }
  for (const c of kids) if (c != null) e.append(c);
  return e;
};
// «1 кадр», «2 кадра», «5 кадров» / «1 frame», «5 frames»
function framesText(n) {
  if (lang !== "ru") return `${n} ${n === 1 ? "frame" : "frames"}`;
  const d = n % 10, h = n % 100;
  return `${n} ${d === 1 && h !== 11 ? "кадр" : d >= 2 && d <= 4 && (h < 12 || h > 14) ? "кадра" : "кадров"}`;
}
function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
  $("clip-loop").setAttribute("aria-label",t("clip_loop"));
  document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = t(n.dataset.i18nTitle); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });
  $("lang").textContent = lang === "ru" ? "EN" : "RU";
  for (const [id, ru, en] of [["prev-frame", "Предыдущий кадр", "Previous frame"], ["next-frame", "Следующий кадр", "Next frame"], ["play", "Пуск / пауза", "Play / pause"],
    ["seek", "Позиция", "Position"], ["speed", "Скорость", "Speed"], ["t-name", "Название дубля", "Take name"], ["person-select", "Участник", "Participant"],
    ["issue-list", "Кадры для проверки", "Frames to review"], ["clip-history", "Экспортированные фрагменты", "Exported clips"]])
    $(id)?.setAttribute("aria-label", lang === "ru" ? ru : en);
  $("lang").title = lang === "ru" ? "Язык" : "Language";
  if (STATUS) workbench.refreshProfiles?.().catch(() => {});
  if (UPDATE?.available) $("update-pill").textContent = t("update_available").replace("{v}", UPDATE.version);
  if (STATUS) refreshCharacters($("char-select").value).catch(() => {});
  renderAll();
}

// ---------------------------------------------------------------- API
const TOKEN = new URLSearchParams(location.search).get("t") || "";
const withT = (u) => u + (u.includes("?") ? "&" : "?") + "t=" + encodeURIComponent(TOKEN);
async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  opts.headers = { ...(opts.headers || {}), "X-MoCapGate-Token": TOKEN };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
function upload(file, onProgress) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", withT("/api/upload?name=" + encodeURIComponent(file.name)));
    x.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    x.onload = () => { const d = JSON.parse(x.responseText || "{}"); x.status === 200 ? resolve(d) : reject(new Error(d.error || x.statusText)); };
    x.onerror = () => reject(new Error("network"));
    x.send(file);
  });
}
function toast(msg, bad = false) {
  const n = $("toast"); n.textContent = msg; n.className = "toast" + (bad ? " bad" : "");
  clearTimeout(toast.h); toast.h = setTimeout(() => n.classList.add("hidden"), Math.max(bad ? 7000 : 3500, msg.length * 55));
}
// ошибки сервера и конвейера — по-русски; в английском интерфейсе переводим самые частые
const ERR_EN = [
  [/этот дубль уже обрабатывается/, "This take is already being processed"],
  [/дубль не найден/, "Take not found — it may have been deleted"],
  [/дождитесь завершения обработки, затем переименуйте/, "Wait for processing to finish, then rename the take"],
  [/дождитесь завершения обработки/, "Wait for the take to finish processing"],
  [/Дубль уже в очереди/, "The take is already queued"],
  [/неизвестные настройки/, "Unknown settings"],
  [/архив повреждён или не докачан/, "The archive is damaged or incomplete — download it again"],
  [/нужно видео, результат GVHMR или BVH/, "Add a video, a GVHMR result or a BVH"],
  [/неизвестный тип файла: (.*)/, "Unsupported file type: $1"],
  [/Установите GEM-X/, "Install GEM-X in Models & tools"],
  [/В файле нет видеодорожки/, "The file has no video track — choose another video"],
  [/Не удалось прочитать видео(.*)/, "Could not read the video$1"],
  [/Не удалось перекодировать видео(.*)/, "Could not convert the video$1"],
  [/Не удалось привести видео к 30 FPS(.*)/, "Could not convert the video to 30 FPS$1"],
  [/загруженный файл не найден/, "Uploaded file not found — drop it again"],
  [/Для FBX нужен Blender|Blender не найден/, "Blender is required for FBX — install it in Models & tools"],
  [/Сначала обработайте дубль|сначала обработайте дубль/, "Process the take first"],
  [/FPS экспорта должен быть от 0 до 1000/, "Export FPS must be between 0 and 1000 (0: source video)"],
  [/WSL не отвечает/, "WSL is not responding — restart the computer or run wsl --shutdown"],
  [/установите Command Line Tools/, "Install the Command Line Tools: xcode-select --install"],
  [/превышено время ожидания/, "Timed out — check the internet connection and try again"],
  [/Недостаточно места|мало места|свободно/, "Not enough free disk space — free some space and try again"],
  [/RTX 50/, "RTX 50-series GPUs are not supported by GVHMR yet — use GEM-X or Colab"],
  [/NVIDIA/, "An NVIDIA GPU with CUDA is required for this model"],
  [/Подтвердите условия/, "Accept the model terms first"],
  [/Выберите участника/, "Select a participant"],
  [/Диапазон должен/, "The range must be whole frames within the take"],
  [/персонаж не найден/, "Character not found — upload it again"],
  [/дождитесь окончания обработки/, "Wait until processing finishes"],
  [/для GEM-X нужно видео/, "GEM-X needs a video; open a GVHMR result with GVHMR"],
  [/к дублю можно добавить видео/, "Only a video or a Colab result can be added to a take"],
  [/Не найден ffmpeg/, "ffmpeg not found — install it in Models & tools"],
  [/Скелет записи не подходит к Man_Rig/, "The capture skeleton does not fit Man_Rig: choose the capture skeleton or your own rig in Settings"],
];
const errorText = (msg) => {
  msg = String(msg || "");
  if (lang !== "en") return msg;
  for (const [re, en] of ERR_EN) { const m = msg.match(re); if (m) return en.replace("$1", (m[1] || "").replace("(код ", "(code ")); }
  return msg;
};
const fail = (e) => toast(errorText(e.message || e), true);
const openUrl = (url) => api("/api/open-url", { url }).catch(() => window.open(url, "_blank", "noopener"));

// ---------------------------------------------------------------- состояние
let STATUS = null;
let TAKES = [];
let CURRENT = null;      // id открытого дубля
let TAKE = null;         // его данные
let newBackend = "";
let picked = [];         // [{file, id?, progress}]

async function loadStatus(refresh = false) {
  STATUS = await api("/api/status" + (refresh ? "?refresh=1" : ""));
  if (!lang) lang = STATUS.settings.lang || ((navigator.language || "en").toLowerCase().startsWith("ru") ? "ru" : "en");
  newBackend = newBackend || (STATUS.settings.backend === "mediapipe" ? "gvhmr-colab" : STATUS.settings.backend);
  $("open-browser").classList.toggle("hidden", !STATUS.desktop);  // в браузере кнопка бессмысленна
}
function renderAll() {
  if (!STATUS) return;
  workbench.labels();
  renderPills(); renderStatus(); renderSettings(); renderTakeList(); renderBackendCards();
  if (STATUS.setup_job && !watching.has(STATUS.setup_job)) {
    setupRunning = true;
    renderStatus();
    watchJob(STATUS.setup_job,$('setup-job'),$('setup-bar'),$('setup-text'),async () => {
      setupRunning = false;
      await loadStatus(true); renderAll();
    });
  }
  buildOptions($("new-opt-grid"), STATUS.settings, newBackend, "new");
  if (TAKE) renderTake();
}
function renderPills() {
  const c = STATUS.components, p = $("pills"); p.replaceChildren();
  const pill = (ok, text) => p.append(el("span", { class: "pill " + (ok ? "ok" : "bad"), text }));

  pill(!!c.gemx?.ready, "GEM-X");
  if (c.gvhmr_local.ready) pill(true, "GVHMR " + t("this_pc"));
  else p.append(el("span", { class: "pill", text: "GVHMR · Colab" }));  // Colab работает и без локальной установки
  pill(!!c.blender.path, "Blender");
  if (c.maya.path) pill(true, "Maya");
  pill(!!c.ffmpeg.path, "ffmpeg");
}

// ---------------------------------------------------------------- вкладки
let view = "takes";
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
function showView(v) {
  view = v;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
  document.querySelectorAll(".view").forEach((n) => n.classList.toggle("hidden", n.id !== "view-" + v));
  if (v !== "camera") stopCamera();
  else listCameras().catch(() => {});  // до разрешения названия камер пустые — заполнятся после включения
  if (v === "status" || v === "settings") loadStatus().then(renderAll).catch(fail);
  if (v === "status" && !PREFLIGHT && !$("pf-run").disabled) runPreflight();
  if (v === "status") loadBench();
  document.querySelectorAll(".tab").forEach(b => b.setAttribute("aria-selected",String(b.dataset.view===v)));
}

// ---------------------------------------------------------------- настройки обработки (общая форма)
const OPTS = [
  { k: "mixamo_namespace", type: "check", label: "o_mixamo_namespace" },
  { k: "body_surface", type: "check", for: ["mediapipe", "gvhmr-colab", "gvhmr-local", "gvhmr-file"], label: "o_surface" },
  { k: "capture_hands", type: "check", for: ["mediapipe", "gvhmr-colab", "gvhmr-local", "gvhmr-file"], label: "o_hands" },
  { k: "gvhmr_hands", type: "select", for: ["gvhmr-colab", "gvhmr-local", "gvhmr-file"], vals: ["auto", "gemx", "mediapipe"], label: "o_gvhmr_hands", vl: (v) => t("o_gvhmr_hands_" + v), hint: "o_gvhmr_hands_hint", def: "auto" },
  { k: "capture_face", type: "check", for: ["mediapipe", "gvhmr-colab", "gvhmr-local", "gvhmr-file", "gemx-local"], label: "o_face" },
  { k: "max_people", type: "number", for: ["mediapipe", "gvhmr-local", "gemx-local"], min: 1, max: 8, step: 1, label: "o_people" },
  { k: "single_actor_multiview", type: "check", for: ["mediapipe", "gvhmr-local", "gemx-local"], label: "o_single_actor_multiview", hint: "o_single_actor_multiview_hint" },
  { k: "view_crop", type: "select", for: ["mediapipe", "gvhmr-local", "gemx-local"], vals: ["full", "left", "right"], label: "o_view_crop", vl: (v) => t("o_view_crop_" + v), hint: "o_view_crop_hint", def: "full" },
  // GEM-X: режим модели, камера, детектор и трекер — чтобы раскрыть модель на сложном видео
  { k: "gvhmr_min_seconds", type: "number", for: ["gvhmr-local"], min: 0.05, max: 10, step: 0.05, label: "o_gemx_min", hint: "o_gemx_min_hint", def: 0.25 },
  { k: "gemx_quality", type: "select", for: ["gemx-local"], vals: ["fast", "accurate", "max"], label: "o_gemx_quality", vl: (v) => t("o_gemx_q_" + v), hint: "o_gemx_quality_hint", def: "fast" },
  { k: "gemx_fps", type: "select", for: ["gemx-local"], vals: ["30", "0"], label: "o_gemx_fps", vl: (v) => t("o_gemx_fps_" + v), hint: "o_gemx_fps_hint", def: "30" },
  { k: "gemx_chunk_seconds", type: "select", for: ["gemx-local"], vals: ["-1", "0", "15", "30", "60"], label: "o_chunk", vl: (v) => v === "-1" ? t("o_chunk_auto") : v === "0" ? t("o_chunk_off") : `${v} ${lang === "ru" ? "с" : "s"}`, hint: "o_chunk_hint", def: "-1" },
  { k: "recognition_max_px", type: "select", for: ["gemx-local", "gvhmr-local"], vals: ["1280", "1920", "0"], label: "o_max_px", vl: (v) => v === "0" ? t("o_max_px_0") : `${v} px`, hint: "o_max_px_hint", def: "1920" },
  { k: "gemx_f_mm", type: "number", for: ["gemx-local"], min: 0, max: 400, step: 1, label: "o_gemx_f", hint: "o_gemx_f_hint", def: 0 },
  { k: "gemx_score", type: "range", for: ["gemx-local"], min: 0.1, max: 0.9, step: 0.05, label: "o_gemx_score", hint: "o_gemx_score_hint", def: 0.5 },
  { k: "gemx_min_seconds", type: "number", for: ["gemx-local"], min: 0.05, max: 10, step: 0.05, label: "o_gemx_min", hint: "o_gemx_min_hint", def: 0.25 },
  { k: "gemx_track_memory", type: "number", for: ["gemx-local"], min: 1, max: 600, step: 1, label: "o_gemx_memory", hint: "o_gemx_memory_hint", def: 30 },
  { k: "hand_stability", type: "check", label: "o_hand_stability" },
  { k: "smooth_body", type: "range", min: 0, max: 1, step: 0.05, label: "o_smooth_body", hint: "o_smooth_hint", def: 0 },
  { k: "smooth_hands", type: "range", min: 0, max: 1, step: 0.05, label: "o_smooth_hands", def: 0 },
  { k: "smoothing", type: "range", for: ["mediapipe"], min: 0, max: 1, step: 0.05, label: "o_smoothing" },
  { k: "root", type: "select", vals: ["image", "inplace"], label: "o_root", vl: (v) => t("o_root_" + v) },
  { k: "foot_lock", type: "check", label: "o_foot_lock" },
  { k: "focal_mm", type: "number", for: ["mediapipe"], min: 0, max: 400, step: 1, label: "o_focal", hint: "o_focal_hint" },
  { k: "space", type: "select", for: ["gvhmr-colab", "gvhmr-local", "gvhmr-file"], vals: ["global", "incam"], label: "o_space", vl: (v) => t("o_space_" + v) },
  { k: "static_camera", type: "check", for: ["gvhmr-local"], label: "o_static" },
  { k: "gvhmr_f_mm", type: "number", for: ["gvhmr-local"], min: 0, max: 400, step: 1, label: "o_gvhmr_f" },
  { k: "export_fps", type: "select", for: ["take"], vals: ["0","30","60","120"], label: "o_fps", vl: (v) => v === "0" ? (lang === "ru" ? "Как у исходного видео" : "Same as source video") : v + " FPS" },
];
function buildOptions(grid, values, backend, mode) {
  grid.replaceChildren();
  grid.append(el("small", { style: "grid-column: 1 / -1", text: backend === "gemx-local" ? (lang === "ru" ? "SOMA: тело, пальцы, глаза и челюсть уже в скелете. «Полное лицо и мимика» добавляет 52 кривые выражений (CSV, Maya, blend shapes в FBX) по каждому участнику. Камера статичная; людей — сколько задано ниже." : "SOMA: body, fingers, eyes and jaw are in the skeleton. “Full face and expressions” adds 52 expression curves (CSV, Maya, FBX blend shapes) per participant. Static camera; as many people as set below.") : t("o_detail_hint") }));
  const SETTINGS_KEYS = ["hand_stability", "smooth_body", "smooth_hands", "root", "foot_lock", "focal_mm", "space", "max_people", "capture_hands", "capture_face", "body_surface", "mixamo_namespace"];  // значения по умолчанию
  for (const o of OPTS) {
    // у GEM-X свои кисти и лицо (SOMA) — захват MediaPipe и поверхность SMPL-X к нему не относятся
    if (backend === "gemx-local" && mode !== "settings" && !o.k.startsWith("gemx_") && !["export_fps", "hand_stability", "max_people", "single_actor_multiview", "mixamo_namespace", "root", "capture_face", "foot_lock", "smooth_body", "smooth_hands", "recognition_max_px"].includes(o.k)) continue;
    if (mode === "settings") { if (!SETTINGS_KEYS.includes(o.k) || o.k === "focal_mm") continue; }
    else if (o.k === "export_fps") { if (mode !== "take" && mode !== "new") continue; }
    else if (o.for && !o.for.includes(backend)) continue;
    const v = (o.k === "export_fps" ? String(values.export_fps ?? values.fps ?? 0) : values[o.k]) ?? o.def ?? (o.type === "check" ? false : o.type === "number" ? 0 : "");
    let input;
    if (o.type === "select") {
      input = el("select", { "data-k": o.k });
      for (const val of o.vals) input.append(el("option", { value: val, text: o.vl ? o.vl(val) : val }));
      const saved = String(v);
      if (o.k === "gemx_chunk_seconds" && /^\d+$/.test(saved) && Number(saved) >= 5 && Number(saved) <= 600 && !o.vals.includes(saved)) {
        input.append(el("option", { value: saved, text: o.vl(saved) }));
      }
      input.value = o.k === "export_fps" && !o.vals.includes(v) ? "0" : v;
    } else if (o.type === "range") {
      const out = el("span", { class: "mono", text: Number(v).toFixed(2) });
      input = el("input", { type: "range", min: o.min, max: o.max, step: o.step, value: v, "data-k": o.k,
        oninput: (e) => { out.textContent = Number(e.target.value).toFixed(2); } });
      grid.append(el("label", { class: "field" }, el("span", { text: t(o.label) + " " }, out), input, o.hint ? el("small", { text: t(o.hint) }) : null));
      continue;
    } else if (o.type === "check") {
      input = el("input", { type: "checkbox", "data-k": o.k });
      input.checked = !!v;
      grid.append(el("label", { class: "check" }, input, el("span", { text: t(o.label) })),
        o.hint ? el("small", { style: "grid-column: 1 / -1", text: t(o.hint) }) : null);
      continue;
    } else {
      input = el("input", { type: "number", min: o.min, max: o.max, step: o.step, value: v, "data-k": o.k });
    }
    grid.append(el("label", { class: "field" }, el("span", { text: t(o.label) }), input, o.hint ? el("small", { text: t(o.hint) }) : null));
  }
  const singleActor = grid.querySelector('[data-k="single_actor_multiview"]');
  const people = grid.querySelector('[data-k="max_people"]');
  if (singleActor && people) {
    const saved = String(people.value || 4);
    const sync = () => {
      if (singleActor.checked) {
        if (!people.disabled) people.dataset.savedMaxPeople = people.value;
        people.value = "1";
        people.disabled = true;
      } else {
        people.disabled = false;
        people.value = people.dataset.savedMaxPeople || saved;
        delete people.dataset.savedMaxPeople;
      }
    };
    singleActor.addEventListener("change", sync);
    sync();
  }
}
// настройки в форме отличаются от тех, с которыми получена текущая анимация
function markChanged() {
  const tk = TAKE, used = tk?.processed_options || tk?.options;  // старые дубли — без processed_options
  let changed = false;
  if (tk && tk.status === "done" && used) {
    const now = readOptions($("take-opt-grid"));
    changed = Object.entries(now).some(([k, v]) => k in used ? String(used[k]) !== String(v) : k === "export_fps" ? String(v) !== String(used.fps ?? 0) && String(v) !== "0" : k === "single_actor_multiview" ? !!v : k === "view_crop" ? v !== "full" : false);
  }
  $("options-changed").classList.toggle("hidden", !changed);
  $("reprocess").classList.toggle("primary", changed || tk?.status !== "done");
}
$("take-opt-grid").addEventListener("input", markChanged);
$("take-opt-grid").addEventListener("change", markChanged);
async function showQueued(id) {
  const q = await api("/api/queue");
  const item = (q.items || []).find((i) => i.id === id && i.state === "waiting");
  if (CURRENT !== id) return;
  $("t-queued").classList.toggle("hidden", !item);
  $("t-queue-start").classList.toggle("hidden", !q.paused);
  $("t-queued-text").textContent = t(q.paused ? "queued_paused" : "queued_waiting");
}
$("t-queue-start").addEventListener("click", async () => { try { await api("/api/queue", { action: "resume" }); showQueued(CURRENT); } catch (e) { fail(e); } });
$("t-open-models").addEventListener("click", () => showView("status"));
function readOptions(grid) {
  const out = {};
  grid.querySelectorAll("[data-k]").forEach((n) => {
    const o = OPTS.find((x) => x.k === n.dataset.k);
    out[n.dataset.k] = o.type === "check" ? n.checked : (o.type === "number" || o.type === "range") ? Number(n.value) : n.value;
  });
  if (out.single_actor_multiview) out.max_people = 1;
  return out;
}

// ---------------------------------------------------------------- новый дубль
let creatingTake = false;
const backendReady = (b) => b === "gvhmr-colab" || (b === "gvhmr-local" ? STATUS.components.gvhmr_local.ready : b === "gemx-local" ? Boolean(STATUS.components.gemx?.ready) : b === "multiview-local" ? Boolean(STATUS.components.mediapipe?.installed) : true);
function renderBackendCards() {
  const c = STATUS.components;
  document.querySelectorAll("#backend-cards .card").forEach((b) => {
    b.classList.toggle("on", b.dataset.backend === newBackend);
    if (b.dataset.backend === "gvhmr-local") b.title = c.gvhmr_local.ready ? "" : t("need_local");
    const missing = !backendReady(b.dataset.backend);
    let tag = b.querySelector(".tag-missing");
    if (missing && !tag) b.append(tag = el("em", { class: "tag-missing" }));
    if (tag) { tag.textContent = t("not_installed"); tag.classList.toggle("hidden", !missing); }
  });
  $("colab-steps").classList.toggle("hidden", newBackend !== "gvhmr-colab");
  updateStart();
}
document.querySelectorAll("#backend-cards .card").forEach((b) => b.addEventListener("click", () => {
  newBackend = b.dataset.backend; renderBackendCards(); buildOptions($("new-opt-grid"), STATUS.settings, newBackend, "new");
}));
function updateStart() {
  const c = STATUS?.components;
  let hint = "";
  const ready = picked.length && picked.every((p) => p.id);
  const onlyResults = picked.length && picked.every((p) => !/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(p.file.name));
  if (!picked.length) hint = t("pick_files");
  else if (newBackend === "multiview-local" && (picked.length !== 1 || !/\.zip$/i.test(picked[0].file.name))) hint = t("multiview_zip_hint");
  else if (newBackend === "multiview-local" && !c.mediapipe.installed) hint = t("need_mediapipe");
  else if (!onlyResults && newBackend === "mediapipe" && !c.mediapipe.installed) hint = t("need_mediapipe");
  else if (!onlyResults && newBackend === "gvhmr-local" && !c.gvhmr_local.ready) hint = t("need_local");
  else if (!onlyResults && newBackend === "gemx-local" && !c.gemx?.ready) hint = lang === "ru" ? "Установите GEM-X в разделе моделей" : "Install GEM-X in Models & tools";
  else if ($("batch-mode").checked && newBackend === "multiview-local") hint = t("multiview_batch_hint");
  else if ($("batch-mode").checked && !["gvhmr-local", "gemx-local"].includes(newBackend)) hint = lang === "ru" ? "Несколько видео в очередь — только с GEM-X или GVHMR на этом ПК" : "A batch needs GEM-X or GVHMR on this PC";
  else if (newBackend === "gvhmr-colab" && !onlyResults) hint = t("colab_video_hint");
  $("start-hint").textContent = hint;
  const needsInstall = hint && hint !== t("pick_files") && hint !== t("colab_video_hint");
  $("start-hint").classList.toggle("link", Boolean(needsInstall));
  $("start-hint").onclick = needsInstall ? () => showView("status") : null;
  $("start").disabled = creatingTake || !ready || (newBackend === "multiview-local" && (picked.length !== 1 || !/\.zip$/i.test(picked[0]?.file.name || "") || !c.mediapipe.installed)) || ($("batch-mode").checked && !["gvhmr-local", "gemx-local"].includes(newBackend)) || (!onlyResults && ((newBackend === "mediapipe" && !c.mediapipe.installed) ||
    (newBackend === "gvhmr-local" && !c.gvhmr_local.ready) || (newBackend === "gemx-local" && !c.gemx?.ready)));
}
function releasePickedPreview(p) {
  if (p?.previewUrl) { URL.revokeObjectURL(p.previewUrl); p.previewUrl = ""; }
}
function renderPicked() {
  const box = $("picked"); box.replaceChildren();
  for (const p of picked) {
    p.progressFill = el("i", { style: `width:${Math.round((p.progress || 0) * 100)}%` });
    const bar = el("div", { class: "bar" }, p.progressFill);
    p.statusNode = el("small", { text: p.error ? errorText(p.error) : p.id ? t("uploaded") : `${(p.file.size / 2 ** 20).toFixed(1)} MB` });
    const item = el("div", { class: "picked-file" }, el("span", { text: p.file.name }), bar,
      p.statusNode,
      el("button", { class: "ghost small", type: "button", text: "×", title: lang === "ru" ? "Убрать" : "Remove", "aria-label": lang === "ru" ? "Убрать файл" : "Remove file",
        onclick: () => {
          const index = picked.indexOf(p);
          if (index >= 0) picked.splice(index, 1);
          releasePickedPreview(p);
          renderPicked();
        } }));
    if (p.previewUrl) {
      if (!p.previewNode) {
        const unavailable = el("small", { class: "picked-preview-error hidden", text: t("preview_unavailable") });
        const video = el("video", { class: "picked-preview", controls: "", playsinline: "", muted: "", preload: "metadata", src: p.previewUrl,
          "aria-label": `${lang === "ru" ? "Предпросмотр" : "Preview"}: ${p.file.name}` });
        const meta = el("small", { class: "picked-preview-meta", text: t("preview_loading") });
        video.addEventListener("loadedmetadata", () => {
          const duration = Number.isFinite(video.duration) ? `${video.duration.toFixed(1)} ${lang === "ru" ? "с" : "s"}` : "";
          meta.textContent = [video.videoWidth && video.videoHeight ? `${video.videoWidth}×${video.videoHeight}` : "", duration].filter(Boolean).join(" · ") || t("preview_loading");
        });
        video.addEventListener("error", () => unavailable.classList.remove("hidden"));
        p.previewNode = el("div", { class: "picked-preview-wrap" }, meta, video, unavailable);
      }
      item.append(p.previewNode);
    }
    box.append(item);
  }
  // несколько видео в один дубль — использовалось бы только последнее
  const videos = picked.filter((p) => /\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(p.file.name)).length;
  if (videos > 1 && !$("batch-mode").checked) {
    $("batch-mode").checked = true;
    toast(lang === "ru" ? "Несколько видео — включён режим «отдельный дубль на каждое видео»." : "Several videos — each will become its own take (batch mode on).");
  }
  updateStart();
}
async function addFiles(files) {
  for (const file of files) {
    const p = { file, progress: 0 };
    if (/\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(file.name)) p.previewUrl = URL.createObjectURL(file);
    picked.push(p);
    if (!$("take-name").value) $("take-name").value = file.name.replace(/(\.mocapgate)?\.[^.]+$/, "").replace(/_mocapgate$/, "");
    renderPicked();
    upload(file, (f) => {
      p.progress = f;
      if (p.progressFill) p.progressFill.style.width = `${Math.round(f * 100)}%`;
    })
      .then((d) => { p.id = d.id; p.progress = 1; if (p.progressFill) p.progressFill.style.width = "100%"; if (p.statusNode) p.statusNode.textContent = t("uploaded"); updateStart(); })
      .catch((e) => { p.error = e.message; if (p.statusNode) p.statusNode.textContent = errorText(e.message); updateStart(); });
  }
}
window.addEventListener("pagehide", () => {
  for (const p of picked) releasePickedPreview(p);
}, { once: true });
function wireDrop(zone, input, onFiles) {
  zone.addEventListener("click", (e) => {
    if (e.target !== input) { e.preventDefault(); input.click(); }
  });
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  input.addEventListener("change", () => { onFiles([...input.files]); input.value = ""; });
  zone.addEventListener("dragover", (e) => {
    if (!e.dataTransfer?.types.includes("Files")) return;
    e.preventDefault(); e.dataTransfer.dropEffect = "copy"; zone.classList.add("over");
  });
  zone.addEventListener("dragleave", (e) => {
    if (!zone.contains(e.relatedTarget)) zone.classList.remove("over");
  });
  zone.addEventListener("drop", (e) => {
    e.preventDefault(); e.stopPropagation(); zone.classList.remove("over");
    const files = [...(e.dataTransfer?.files || [])];
    if (files.length) onFiles(files);
  });
}
wireDrop($("drop"), $("file-input"), addFiles);
// бросить файл в любое место вкладки «Дубли» — тоже новый дубль
$("view-takes").addEventListener("dragover", (e) => e.preventDefault());
$("view-takes").addEventListener("drop", (e) => {
  if (e.defaultPrevented) return;
  e.preventDefault();
  const files = [...(e.dataTransfer?.files || [])];
  if (files.length) { showNew(); addFiles(files); }
});
// A file dropped outside an import zone must not navigate away from Studio.
for (const type of ["dragover", "drop"]) document.addEventListener(type, (e) => {
  if (e.dataTransfer?.types.includes("Files")) e.preventDefault();
});
$("new-take").addEventListener("click", showNew);
// загруженные, но не превращённые в дубль файлы не пропадают молча
const pendingImport = () => picked.some((p) => p.id) && !creatingTake && !$("new-panel").classList.contains("hidden");
function confirmLeaveImport() { return !pendingImport() || confirm(t("leave_import")); }
function showNew() {
  CURRENT = null; TAKE = null; for (const p of picked) releasePickedPreview(p); picked = []; renderPicked(); $("take-name").value = "";
  $("new-panel").classList.remove("hidden"); $("take-panel").classList.add("hidden"); renderTakeList();
}
$("start").addEventListener("click", async () => {
  if (creatingTake) return;
  creatingTake = true;
  try {
    $("start").disabled = true;
    if ($('batch-mode').checked) {
      if (!['gvhmr-local','gemx-local'].includes(newBackend)) throw Error(lang==='ru'?'Для очереди выберите локальный GVHMR или GEM-X':'Choose local GVHMR or GEM-X for a batch');
      if (picked.some(p=>! /\.(mp4|mov|webm|avi|mkv|m4v)$/i.test(p.file.name))) throw Error(lang==='ru'?'Пакетная загрузка принимает только видео':'Batch upload accepts video files only');
      while(picked.length) {
        const p=picked[0];await api('/api/takes',{files:[p.id],name:p.file.name.replace(/\.[^.]+$/,''),backend:newBackend,options:readOptions($('new-opt-grid')),queue:true});
        releasePickedPreview(p);picked.shift();renderPicked();
      }
      await loadTakes();await workbench.queueRefresh();document.querySelector('.queue-panel').open=true;toast(lang==='ru'?'Дубли добавлены в очередь и обрабатываются по одному.':'Takes queued — they are processed one at a time.');return;
    }
    const d = await api("/api/takes", { files: picked.map((p) => p.id), name: $("take-name").value.trim(), backend: newBackend,
      options: readOptions($("new-opt-grid")), source: "file", original_name: picked[0]?.file.name, project: $("project-filter").value.replace(/^-$/, "") });
    for (const p of picked) releasePickedPreview(p); picked = []; renderPicked();
    toast(d.job ? t("started") : t("st_waiting"));
    await loadTakes(); openTake(d.id, d.job);
  } catch (e) { fail(e); } finally { creatingTake=false;updateStart(); }
});
function openColab() {
  openUrl(STATUS.colab_url);
  toast(t("colab_private_hint"));
}
$("open-colab").addEventListener("click", openColab);
$("open-colab-2").addEventListener("click", openColab);
$("dl-notebook").href = $("dl-notebook-2").href = withT("/api/colab-notebook");
document.addEventListener("click", (e) => {  // ноутбук в окне приложения — тоже через «Загрузки»
  const a = e.target.closest?.('a[href*="/api/colab-notebook"]');
  if (!a || !STATUS?.desktop) return;
  e.preventDefault();
  api("/api/save-notebook", {}).then((d) => toast(t("saved_to") + d.path)).catch(fail);
});

// ---------------------------------------------------------------- список дублей
async function loadTakes() { TAKES = await api("/api/takes"); renderTakeList(); }
// поиск, проект, статус и выбор нескольких дублей для пакетного экспорта
let takeStatus = "", selectedTakes = new Set();
const BACKEND_NAMES = { "gemx-local": "GEM-X", "gvhmr-local": "GVHMR", "gvhmr-colab": "Colab", "gvhmr-file": "GVHMR", "bvh-file": "BVH", mediapipe: "MediaPipe", "multiview-local": "Multi-camera" };
function visibleTakes() {
  const q = ($("take-search").value || "").trim().toLowerCase(), project = $("project-filter").value;
  return TAKES.filter((tk) => (!project || (project === "-" ? !tk.project : tk.project === project))
    && (!takeStatus || (takeStatus === "waiting" ? tk.status === "waiting-result" : tk.status === takeStatus))
    && (!q || [tk.name, tk.backend, tk.project, ...(tk.tags || []), tk.notes].join(" ").toLowerCase().includes(q)));
}
function renderFilters() {
  const projects = [...new Set(TAKES.map((tk) => tk.project).filter(Boolean))].sort();
  const current = $("project-filter").value;
  $("project-filter").replaceChildren(el("option", { value: "", text: lang === "ru" ? "Все проекты" : "All projects" }),
    ...projects.map((p) => el("option", { value: p, text: p })), el("option", { value: "-", text: lang === "ru" ? "Без проекта" : "No project" }));
  $("project-filter").value = [...$("project-filter").options].some((o) => o.value === current) ? current : "";
  $("project-names").replaceChildren(...projects.map((p) => el("option", { value: p })));
  const chips = [["", lang === "ru" ? "Все" : "All"], ["done", t("st_done")], ["waiting", t("st_waiting")], ["error", t("st_error")], ["new", t("st_new")]];
  $("status-chips").replaceChildren(...chips.map(([v, label]) => el("button", { class: "chip" + (takeStatus === v ? " on" : ""), type: "button", text: label,
    "aria-pressed": String(takeStatus === v), onclick: () => { takeStatus = v; renderTakeList(); } })));
}
function renderTakeList() {
  renderFilters();
  const list = $("take-list"); list.replaceChildren();
  $("no-takes").classList.toggle("hidden", TAKES.length > 0);
  const selecting = $("select-mode").checked;
  selectedTakes = new Set([...selectedTakes].filter((id) => TAKES.some((tk) => tk.id === id && tk.status === "done")));
  $("batch-export").classList.toggle("hidden", !selecting);
  $("batch-count").textContent = (lang === "ru" ? "Выбрано: " : "Selected: ") + selectedTakes.size;
  $("batch-export").querySelectorAll("button").forEach((b) => { b.disabled = !selectedTakes.size || batchRunning || !STATUS?.components.blender.path; });
  for (const tk of visibleTakes()) {
    const st = tk.status === "waiting-result" ? "waiting" : tk.status;
    const badge = tk.status === "done" ? el("span", { class: "badge " + (tk.verdict || ""), text: String(tk.score ?? "") })
      : el("span", { class: "badge", text: t("st_" + st) });
    const pick = selecting && tk.status === "done" ? el("input", { type: "checkbox", "aria-label": tk.name, onclick: (e) => {
      e.stopPropagation(); e.target.checked ? selectedTakes.add(tk.id) : selectedTakes.delete(tk.id); renderTakeList(); } }) : null;
    if (pick) pick.checked = selectedTakes.has(tk.id);
    list.append(el("button", { class: "take-item" + (tk.id === CURRENT ? " on" : "") + (tk.thumb ? " has-thumb" : ""), title: tk.name,
      onclick: () => { if (confirmLeaveImport()) openTake(tk.id); } },
      pick, tk.thumb ? el("img", { class: "thumb", alt: "", loading: "lazy", src: withT(`/files/${tk.id}/thumb.jpg`) }) : null, el("b", { text: tk.name }), badge,
      el("small", { text: [tk.created?.slice(5, 16) || "", BACKEND_NAMES[tk.backend] || tk.backend, tk.frames ? framesText(tk.frames) : "", tk.project || ""].filter(Boolean).join(" · ") }),
      tk.tags?.length ? el("small", { class: "tags", text: tk.tags.map((x) => "#" + x).join(" ") }) : null));
  }
}
$("take-search").addEventListener("input", renderTakeList);
$("batch-mode").addEventListener("change", updateStart);
$("project-filter").addEventListener("change", renderTakeList);
$("select-mode").addEventListener("change", renderTakeList);
// пакетный экспорт: по очереди, по одному дублю (у дубля с несколькими людьми — все одним файлом)
let batchRunning = false;
$("batch-export").querySelectorAll("button[data-preset]").forEach((b) => b.addEventListener("click", async () => {
  const ids = [...selectedTakes]; if (!ids.length) return;
  batchRunning = true; renderTakeList(); let done = 0, failed = [];
  for (const id of ids) {
    try {
      const tk = TAKES.find((x) => x.id === id);
      const d = await api(`/api/takes/${id}/engine`, { preset: b.dataset.preset, root_motion: $("batch-root-motion").checked, all: true, person: null });
      const code = await new Promise((resolve) => { const poll = async () => { const j = await api(`/api/jobs/${d.job}?since=0`).catch(() => ({ done: true, code: 1 })); j.done ? resolve(j.code) : setTimeout(poll, 800); }; poll(); });
      code === 0 ? done++ : failed.push(tk?.name || id);
      $("batch-count").textContent = `${done + failed.length} / ${ids.length}`;
    } catch (e) { failed.push(id); }
  }
  batchRunning = false; await loadTakes(); renderTakeList();
  toast((lang === "ru" ? `Экспортировано: ${done} из ${ids.length}` : `Exported ${done} of ${ids.length}`) + (failed.length ? ` · ${lang === "ru" ? "ошибки" : "failed"}: ${failed.join(", ")}` : ""), failed.length > 0);
}));
$("reveal-library").addEventListener("click", () => api("/api/reveal-library", {}).catch(fail));
setTimeout(() => refreshTrash(), 500);

// ---------------------------------------------------------------- дубль
let overlayData = null;
let overlayPeople = [];
const PERSON_COLORS = ["#f0a35e", "#5cc3cf", "#b493ef", "#e27870", "#9cce72", "#f0ce67", "#89a9ef", "#e992ca"];
const personColor = (id) => PERSON_COLORS[(id-1) % PERSON_COLORS.length];
const allPeopleText = () => lang === "ru" ? "Все участники" : "All participants";
function selectPerson() {
  TAKE = personId === 0 ? { ...sceneTake, bvh: null, fbx: null, maya_scene: null, character_scene: null, character_motion: null, capture_file: null, face_file: null, report: null } :
    { ...sceneTake, fbx: null, engine: null, retargeted: null, ...sceneTake.people.find((p) => p.id === personId), id: sceneTake.id };
}
let viewer3d = null;
let personId = null, sceneTake = null, mediaRequest = 0;
$("person-select").addEventListener("change", () => {
  personId = Number($("person-select").value);
  selectPerson();
  renderTake(true);
});
let optsKey = "";
let openRequest = 0;
async function openTake(id, jobId) {
  const request = ++openRequest;
  if (CURRENT !== id) { personId = null; $("take-panel").scrollTop = 0; optsKey = ""; }
  CURRENT = id;
  $("new-panel").classList.add("hidden"); $("take-panel").classList.remove("hidden");
  renderTakeList();
  const loaded = await api("/api/takes/" + id);
  if (request !== openRequest || CURRENT !== id) return;  // уже открыт другой дубль — не подменять его
  TAKE = loaded;
  sceneTake = TAKE;
  const participants = TAKE.people || [];
  if (participants.length) {
    if (personId !== 0 && !participants.some((p) => p.id === personId)) personId = participants.length > 1 ? 0 : participants[0].id;
    selectPerson();
  }
  overlayData = null;
  renderTake(true);
  showQueued(id).catch(() => {});
  const job = jobId || TAKE.job;
  if (job) watchJob(job, $("job"), $("job-bar"), $("job-text"), () => { if (CURRENT === id) openTake(id); });
}
const busy0 = (tk) => Boolean(tk.job) || tk.status === "processing";
$("wait-reveal").addEventListener("click", () => api(`/api/takes/${CURRENT}/open`, { app: "folder" }).catch(fail));
$("wait-local").addEventListener("click", async () => {
  try { const d = await api(`/api/takes/${CURRENT}/duplicate`, { backend: $("wait-backend").value, name: TAKE?.name });
    toast(lang === "ru" ? "Создан дубль для обработки на этом ПК" : "A take for this PC was created"); await loadTakes(); openTake(d.id, d.job); } catch (e) { fail(e); }
});
$("t-info-save").addEventListener("click", async () => {
  try {
    const d = await api(`/api/takes/${CURRENT}/meta`, { project: $("t-project").value, tags: $("t-tags").value.split(","), notes: $("t-notes").value });
    $("t-info-state").textContent = t("saved"); Object.assign(sceneTake, d); await loadTakes();
  } catch (e) { fail(e); }
});
$("dup-run").addEventListener("click", async () => {
  try {
    const d = await api(`/api/takes/${CURRENT}/duplicate`, { backend: $("dup-backend").value, options: readOptions($("take-opt-grid")) });
    toast(lang === "ru" ? "Создан новый дубль — исходный не изменён" : "New take created — the original is unchanged");
    await loadTakes(); openTake(d.id, d.job);
  } catch (e) { fail(e); }
});
function renderTake(fresh = false) {
  if (TAKE) workbench.review(TAKE,personId).catch(fail);
  const tk = TAKE;
  $("person-picker").classList.toggle("hidden", (tk.people?.length || 0) < 2);
  $("person-select").replaceChildren(...((tk.people?.length || 0) > 1 ? [el("option", { value: 0, text: allPeopleText() })] : []),
    ...(tk.people || []).map((p) => el("option", { value: p.id, text: `${t("person")} ID ${p.id}` })));
  $("person-select").value = personId;
  $("export-person-hint").classList.toggle("hidden", personId !== 0);
  $("export-person-hint").textContent = lang === "ru" ? "Для скачивания или открытия анимации выберите ID участника сверху." : "Select a participant ID above to download or open an animation.";
  $("t-name").value = tk.name;
  if (fresh) {
    $("t-project").value = sceneTake?.project || ""; $("t-tags").value = (sceneTake?.tags || []).join(", "); $("t-notes").value = sceneTake?.notes || "";
    $("t-info-state").textContent = "";
    $("take-info").querySelector("summary").textContent = t("take_info") + (sceneTake?.project || sceneTake?.tags?.length || sceneTake?.notes ? " ●" : "");
  }
  $("dup-run").disabled = busy0(tk) || !tk.input;
  const st = tk.job && tk.status === "error" ? "processing" : tk.status === "waiting-result" ? "waiting" : tk.status;
  $("t-badge").textContent = t("st_" + st) + (tk.status === "done" && tk.score != null && personId !== 0 ? ` · ${tk.score}/100` : "");
  $("t-badge").className = "badge " + (tk.status === "done" ? (tk.verdict === "good" ? "good" : "warn") : tk.status === "error" ? "bad" : "");
  $("t-meta").textContent = [tk.backend, tk.source_fps ? `${Number(tk.source_fps).toFixed(3)} ${lang === "ru" ? "исходное" : "source"} / ${Number(tk.recognition_fps).toFixed(3)} ${lang === "ru" ? "распознавание" : "recognition"} / ${Number(tk.export_fps).toFixed(3)} ${lang === "ru" ? "экспорт" : "export"} FPS${tk.source_vfr ? " · VFR" : ""}` : tk.fps ? `${tk.fps} fps` : "", tk.frames ? framesText(tk.frames) : "", tk.camera_height != null ? t("camera_at").replace("{h}", Number(tk.camera_height).toFixed(2)) : "",
    sceneTake?.resources?.vram_mb ? (lang === "ru" ? `пик: видеопамять ${(sceneTake.resources.vram_mb / 1024).toFixed(1)} ГБ, ОЗУ ${(sceneTake.resources.ram_mb / 1024).toFixed(1)} ГБ` : `peak: VRAM ${(sceneTake.resources.vram_mb / 1024).toFixed(1)} GB, RAM ${(sceneTake.resources.ram_mb / 1024).toFixed(1)} GB`) : "",
    tk.focal_used ? `${t("focal")} ${tk.focal_used} mm` : "", tk.report ? t("bones_" + tk.report.bones) : ""].filter(Boolean).join(" · ");
  $("t-waiting").classList.toggle("hidden", tk.status !== "waiting-result");
  $("t-error").classList.toggle("hidden", !tk.error || busy0(tk)); $("t-error").textContent = errorText(tk.error);
  showAdvice($("t-advice"), tk.error || "");
  // сбой из-за неустановленной модели — сразу путь к установке
  $("t-error-actions").classList.toggle("hidden", !/Установите|установлен|не готов|Install|not ready|not installed/i.test(tk.error || ""));
  const done = tk.status === "done";
  const busy = Boolean(tk.job) || tk.status === "processing";
  $("model-loading").classList.toggle("hidden", !busy || tk.status === "done");
  document.querySelectorAll(".below button, #take-opt-grid input, #take-opt-grid select").forEach(button => { button.disabled = busy; });
  document.querySelectorAll(".below a.button").forEach(link => {
    link.setAttribute("aria-disabled", String(busy));
    link.classList.toggle("export-disabled", busy);
  });
  const rig = STATUS.settings.maya_rig;
  const rigLabel = rig === "builtin" ? "Man_Rig" : rig ? (lang === "ru" ? "свой риг" : "custom rig") : (lang === "ru" ? "скелет распознавания" : "capture skeleton");
  $("export-summary").textContent = busy ? (lang === "ru" ? "Создаётся анимация. Экспорт станет доступен после завершения." : "Creating animation. Export will be available when complete.") :
    `${tk.export_fps || tk.fps || "—"} FPS · ${framesText(tk.frames || 0)} · Maya: ${rigLabel}. ` +
    (tk.character_scene ? (lang === "ru" ? ".ma содержит персонажа Man_Rig со скиннингом и анимацией. BVH/FBX содержат скелет распознавания." : "The .ma contains the skinned, animated Man_Rig character. BVH/FBX contain the capture skeleton.") : (lang === "ru" ? ".ma содержит скелет; кнопка Maya переносит движение на выбранный риг." : "The .ma contains the capture skeleton; the Maya button transfers motion to the selected rig."));
  if (!busy && STATUS.settings.rig_profile) $("export-summary").textContent += lang === "ru" ? ` Профиль «${STATUS.settings.rig_profile}» применяется только при открытии в Maya.` : ` Profile “${STATUS.settings.rig_profile}” applies only when opening in Maya.`;
  $("t-viewer").classList.toggle("hidden", !done && !tk.video);
  const animated = done && Boolean(tk.bvh || tk.people?.length);
  for (const sel of [".transport", ".clip-controls", "#clip-duration", "#strip", "#quality-tools", ".three-col", "#compare-panel"])
    document.querySelector(sel)?.classList.toggle("hidden", !animated);
  $("t-viewer").classList.toggle("video-only", !animated);
  document.querySelector(".below").classList.toggle("hidden", tk.status === "waiting-result");
  $("report").classList.toggle("hidden", !done);
  $("export-block").classList.toggle("hidden", !done);
  $("reprocess").textContent = done ? t("reprocess") : t("process_now");
  $("reprocess").classList.toggle("primary", !done);
  if (done) {
    if (personId === 0) {
      $("score").className = "score hidden";  // число участников в круге читалось как оценка «2/100»
      $("verdict").textContent = `${allPeopleText()}: ${tk.people.length}`;
      $("items").replaceChildren(...tk.people.map((p) => el("li", { class: p.report?.verdict || "" },
        el("b", { text: `${t("person")} ID ${p.id}` }), el("span", { class: "val", text: `${p.report?.score ?? "—"}/100` }))));
    } else renderReport(tk.report);
  }
  const key = `${tk.id}|${tk.backend}|${tk.status}|${JSON.stringify(tk.options || {})}`;
  const edited = optsKey.split("|")[0] === tk.id && optsKey.split("|")[1] === tk.backend ? readOptions($("take-opt-grid")) : {};
  if (key !== optsKey || fresh) {
    buildOptions($("take-opt-grid"), { ...STATUS.settings, ...(tk.options || {}), ...(key === optsKey ? edited : {}) }, tk.backend, "take");
    optsKey = key;
  }
  markChanged();
  $("take-opt-grid").querySelectorAll("input, select").forEach(control => { control.disabled = busy; });  // старые дубли — недостающее из настроек
  $("dl-bvh").href = tk.bvh ? withT(`/files/${tk.id}/${encodeURIComponent(tk.bvh)}?download=1`) : "#";
  $("dl-fbx").classList.toggle("hidden", !tk.fbx);
  if (tk.fbx) $("dl-fbx").href = withT(`/files/${tk.id}/${encodeURIComponent(tk.fbx)}?download=1`);
  $("dl-bvh").classList.toggle("hidden", !tk.bvh);
  $("dl-capture").classList.toggle("hidden", !tk.capture_file || personId === 0);
  if (tk.capture_file) $("dl-capture").href = withT(`/files/${tk.id}/${encodeURIComponent(tk.capture_file)}?download=1`);
  $("dl-audio").classList.toggle("hidden", !sceneTake?.audio);
  if (sceneTake?.audio) $("dl-audio").href = withT(`/files/${tk.id}/${encodeURIComponent(sceneTake.audio)}?download=1`);
  $("dl-face").classList.toggle("hidden", !tk.face_file || personId === 0);
  if (tk.face_file) $("dl-face").href = withT(`/files/${tk.id}/${encodeURIComponent(tk.face_file)}?download=1`);
  const capturePeople = personId === 0 ? tk.people : [tk];
  $("capture-summary").textContent = (capturePeople || []).filter(p => p.capture_counts).map(p => {
    const c = p.capture_counts;
    const id = personId === 0 ? p.id : personId;
    return lang === "ru" ? `ID ${id}: левая кисть ${c.left}/${tk.frames}, правая ${c.right}/${tk.frames}, лицо ${c.face}/${tk.frames}. Пропуски — деталь не распознана. Пальцы — в BVH/FBX; мимика — CSV, Maya и FBX.` :
      `ID ${id}: left hand ${c.left}/${tk.frames}, right ${c.right}/${tk.frames}, face ${c.face}/${tk.frames}. Missing frames were not detected. Fingers: BVH/FBX; expressions: CSV, Maya and FBX.`;
  }).join(" ");
  $("make-fbx").disabled = busy || !STATUS.components.blender.path; $("open-blender").disabled = busy || !STATUS.components.blender.path || personId === 0;
  $("open-blender").title = personId === 0 ? (lang === "ru" ? "Для экспорта выберите ID участника" : "Select a participant ID to export") : "";
  $("open-maya").classList.toggle("hidden", !STATUS.components.maya.path); $("open-maya").disabled = busy || !tk.maya_scene || personId === 0;
  // сцена персонажа — только пока в Настройках выбран встроенный Man_Rig
  const mayaScene = (STATUS?.settings?.maya_rig === "builtin" && tk.character_scene) || tk.maya_scene;
  $("dl-ma").classList.toggle("hidden", !mayaScene);
  if(mayaScene) $("dl-ma").href = withT(`/files/${tk.id}/${encodeURIComponent(mayaScene)}?download=1`);
  $("maya-workflow").classList.toggle("hidden", !tk.character_scene || personId === 0);
  $("dl-maya-tools").classList.toggle("hidden", !tk.maya_tools || personId === 0);
  $("dl-maya-tools").title = lang === "ru" ? "Откройте .ma, затем выполните .py в Maya: Script Editor → Python. Проверка сцены и слой поправок." : "Open the .ma, then run this .py in Maya: Script Editor → Python. Scene checks and correction layer.";
  if(tk.maya_tools) $("dl-maya-tools").href = withT(`/files/${tk.id}/${encodeURIComponent(tk.maya_tools)}?download=1`);
  if (fresh) resetRange();
  renderMarkers();
  $("marker-add").disabled = busy || !tk.bvh;
  $("export-clip").disabled = busy || !tk.bvh || personId === 0;
  if (done) renderEngines(tk);
  for (const id of ["clip-in","clip-out","mark-in","mark-out","clip-reset","clip-inplace"]) $(id).disabled=busy || !tk.bvh;
  if (!STATUS.components.blender.path) $("clip-fbx").checked=false;
  $("clip-fbx").disabled = busy || !STATUS.components.blender.path;
  const clips=(tk.clips || []).filter(c=>c.person===personId);
  $("clip-history").replaceChildren(...clips.slice().reverse().map(c=>el("option",{value:c.archive,text:`${c.first_frame}–${c.last_frame} · ${c.fps} FPS · ${c.root==="inplace-horizontal"?(lang==="ru"?"На месте":"In place"):(lang==="ru"?"С траекторией":"With trajectory")}${c.fbx_content?" · FBX":""}${c.loop?(lang==="ru"?" · цикл":" · loop"):""}${c.root_motion?" · Root":""}${c.edit?.mirror?(lang==="ru"?" · зеркало":" · mirror"):""}${c.edit?.speed?` · ×${c.edit.speed}`:""}`})));
  $("clip-history").classList.toggle("hidden", !clips.length || personId===0);
  updateClipLink();
  $("version-history").classList.toggle("hidden", !(tk.versions?.length));
  $("version-files").replaceChildren(...(tk.versions || []).map(v=>el("div",{class:"version-row"},
    el("a",{class:"button small",text:`${versionDate(v.name)} · ${(v.bytes/1048576).toFixed(1)} MB`,href:withT(`/files/${tk.id}/${v.file}?download=1`),onclick:e=>{
      if(STATUS?.desktop){e.preventDefault();api(`/api/takes/${CURRENT}/save`,{kind:"version",archive:v.file}).then(d=>toast(t("saved_to")+d.path)).catch(fail);}
    }}),
    el("button",{class:"small ghost",text:t("version_restore"),disabled:busy?"":null,onclick:async()=>{
      if(!confirm(t("version_restore_confirm").replace("{d}",versionDate(v.name))))return;
      try{await api(`/api/takes/${CURRENT}/restore`,{version:v.file});toast(t("version_restored"));await loadTakes();openTake(CURRENT);}catch(e){fail(e);}
    }}))));
  if (fresh) loadMedia(tk).catch(fail);
}
let characterGeometry;
async function loadMedia(tk) {
  const request = ++mediaRequest;
  const video = $("video");
  const desiredVideo = tk.video ? withT(`/files/${tk.id}/${encodeURIComponent(tk.video)}`) : null;
  $("media-error").classList.add("hidden");
  if (tk.video) {
    if (video.getAttribute("src") !== desiredVideo) { video.pause(); video.src = desiredVideo; video.load(); }
    $("novideo").classList.add("hidden");
  } else { video.removeAttribute("src"); video.load(); $("novideo").classList.remove("hidden"); }
  const participants = personId === 0 ? tk.people : [tk];
  const loadCharacter = async (p) => {
    if (!p.character_motion || tk.status !== "done") return null;
    const response = await fetch(withT(`/files/${tk.id}/${encodeURIComponent(p.character_motion)}`));
    if (!response.ok) throw Error("Man_Rig: " + response.statusText);
    const info = await response.json();
    if (info.format !== "mocapgate.character-motion/1" || info.geometry_url !== "/ui/rigs/man-rig.json") throw Error("Invalid character motion");
    characterGeometry ||= fetch(info.geometry_url).then(r => { if (!r.ok) throw Error(r.statusText); return r.json(); }).catch(e => { characterGeometry = null; throw e; });
    const binary = await fetch(withT(`/files/${tk.id}/${encodeURIComponent(info.motion_file)}`));
    if (!binary.ok) throw Error("Man_Rig: " + binary.statusText);
    const bytes = await binary.arrayBuffer();
    const geometry = await characterGeometry;
    if (info.bone_count !== geometry.bones.length || info.stride !== 3+4*info.bone_count || !Number.isInteger(info.frames) || bytes.byteLength !== info.frames*info.stride*4) throw Error("Invalid character frames");
    return { ...info, geometry, motion: new Float32Array(bytes) };
  };
  const loadSurface = async (p) => {
    if (!p.mesh_file) return null;
    const response = await fetch(withT(`/files/${tk.id}/${encodeURIComponent(p.mesh_file)}`));
    if (!response.ok) throw Error("SMPL-X: " + response.statusText);
    const info = await response.json();
    const binary = await fetch(withT(`/files/${tk.id}/${encodeURIComponent(info.positions_file)}`));
    if (!binary.ok) throw Error("SMPL-X: " + binary.statusText);
    return { ...info, binary: await binary.arrayBuffer() };
  };
  const media = await Promise.all(participants.map(async (p) => ({ ...p,
    surface: await loadSurface(p), character: await loadCharacter(p),
    overlayData: p.has_overlay ? await fetch(withT(`/files/${tk.id}/${encodeURIComponent(p.overlay || "overlay.json")}`)).then((r) => r.json()).catch(() => null) : null,
    text: tk.status === "done" && p.bvh ? await fetch(withT(`/files/${tk.id}/${encodeURIComponent(p.bvh)}`)).then((r) => { if (!r.ok) throw Error(r.statusText); return r.text(); }) : null,
    color: personColor(p.id === tk.id ? personId || 1 : p.id),
  })));
  if (request !== mediaRequest) return;
  overlayPeople = media;
  overlayData = media.find((p) => p.overlayData)?.overlayData || null;
  document.querySelector(".layers").classList.toggle("hidden", !overlayData);
  drawStrip();
  if (media.some((p) => p.text)) {
    if (!viewer3d) viewer3d = await import("/ui/viewer3d.js").then((m) => m.createViewer($("three")));
    if (request !== mediaRequest) return;
    $("surface-mode").querySelector('[value="character"]').disabled = !media.some(p => p.character);
    $("surface-mode").value = media.some(p => p.character) ? "character" : "surface";
    viewer3d.setMode($("surface-mode").value);
    viewer3d.loadScene(media.filter((p) => p.text));
    peLoad(media.filter((p) => p.text), tk).catch(() => {});
    // камера съёмки: вид из неё в 3D (совпадает с ракурсом видео) — если камера посчитана
    const camFile = tk.camera_file || sceneTake?.camera_file;
    const cam = camFile ? await fetch(withT(`/files/${tk.id}/${encodeURIComponent(camFile)}`)).then((r) => r.ok ? r.json() : null).catch(() => null) : null;
    if (request !== mediaRequest) return;
    $("camera-view").querySelector('[value="capture"]').disabled = !cam;
    if (!cam && $("camera-view").value === "capture") $("camera-view").value = "free";
    viewer3d.setCaptureCamera(cam);
    viewer3d.setView($("camera-view").value);
    viewer3d.setFollow($("camera-follow").checked);
    viewer3d.setView($("camera-view").value);
    const rigs = viewer3d.getStructure(), tree = $("skeleton-tree");
    tree.replaceChildren();
    const buildTree = node => {
      if (!node.children.length) return el("div", { class: "bone-leaf", text: node.name });
      const branch = el("details", { class: "bone-branch" }, el("summary", { text: node.name }));
      branch.open = true;
      node.children.forEach(child => branch.append(buildTree(child)));
      return branch;
    };
    rigs.forEach((root,i) => {
      const participant=media.filter(p=>p.text)[i];
      const displayId = participant.id === tk.id ? personId : participant.id;
      tree.append(el("h4", { text: `${t("person")} ID ${displayId}` }), buildTree(root));
    });
    $("skeleton-panel").classList.toggle("hidden", !rigs.length);
    $("surface-mode-wrap").classList.toggle("hidden", !media.some(p => p.surface || p.character));
    viewer3d.setMode($("surface-mode").value);
  } else { viewer3d?.clear(); $("skeleton-panel").classList.add("hidden"); }
  syncFrame();
}
$("camera-view").addEventListener("change", () => {viewer3d?.setView($("camera-view").value);workbench.camera($("camera-view").value,$("camera-follow").checked);});
$("camera-follow").addEventListener("change", () => {viewer3d?.setFollow($("camera-follow").checked);workbench.camera($("camera-view").value,$("camera-follow").checked);});
$("surface-mode").addEventListener("change", () => viewer3d?.setMode($("surface-mode").value));
$("t-name").addEventListener("change", () => {
  if (!$("t-name").value.trim()) { $("t-name").value = TAKE?.name || ""; return; }  // пустое имя сервер не примет — вернуть прежнее
  api(`/api/takes/${CURRENT}/rename`, { name: $("t-name").value }).then(loadTakes).catch((e) => { $("t-name").value = TAKE?.name || ""; fail(e); });
});
const mb = (bytes) => `${(bytes / 2 ** 20).toFixed(bytes < 2 ** 20 ? 2 : 0)} MB`;
$("t-delete").addEventListener("click", async () => {
  if (!confirm(t("confirm_delete"))) return;
  // плеер держит видеофайл открытым — на Windows такой файл не удалить
  const v = $("video"); v.pause(); v.removeAttribute("src"); v.load();
  $("t-delete").disabled = true;
  try { const d = await api(`/api/takes/${CURRENT}/delete`, {}); toast(t("deleted") + mb(d.freed || 0)); await loadTakes(); showNew(); }
  catch (e) { fail(e); } finally { $("t-delete").disabled = false; }
});
async function refreshTrash() {
  const info = await api("/api/trash").catch(() => null);
  const b = $("empty-trash");
  b.classList.toggle("hidden", !info?.count);
  if (info?.count) b.textContent = `${t("trash_empty")} · ${info.count} · ${mb(info.bytes)}`;
}
$("empty-trash").addEventListener("click", async () => {
  if (!confirm(t("confirm_trash"))) return;
  try { const d = await api("/api/trash/empty", {}); toast(t("trash_done") + mb(d.bytes || 0)); refreshTrash(); } catch (e) { fail(e); }
});
$("reprocess").addEventListener("click", async () => {
  try { const d = await api(`/api/takes/${CURRENT}/process`, { options: readOptions($("take-opt-grid")) }); openTake(CURRENT, d.job); } catch (e) { fail(e); }
});
$("make-fbx").addEventListener("click", async () => {
  try { const d = await api(`/api/takes/${CURRENT}/fbx`, {}); watchJob(d.job, $("job"), $("job-bar"), $("job-text"), (job) => { if (job.code === 0) toast(t("fbx_done")); openTake(CURRENT); }); } catch (e) { fail(e); }
});
// в окне приложения скачивание идёт через сервер: файл копируется в «Загрузки» и показывается в папке
for (const [id, kind] of [["dl-maya-tools", "maya_tools"], ["dl-bvh", "bvh"], ["dl-fbx", "fbx"], ["dl-ma", "maya_scene"], ["dl-capture", "capture_file"], ["dl-face", "face_file"], ["dl-audio", "audio"]]) {
  $(id).addEventListener("click", (e) => {
    if ((personId === 0 && kind !== "audio") || TAKE?.job || TAKE?.status === "processing") { e.preventDefault(); return; }
    if (!STATUS?.desktop) return;
    e.preventDefault();
    api(`/api/takes/${CURRENT}/save`, { kind: kind === "maya_scene" && TAKE?.character_scene && STATUS?.settings?.maya_rig === "builtin" ? "character_scene" : kind, person: personId }).then((d) => toast(t("saved_to") + d.path)).catch(fail);
  });
}
$("open-blender").addEventListener("click", () => api(`/api/takes/${CURRENT}/open`, { app: "blender", person: personId }).catch(fail));
$("open-maya").addEventListener("click", () => api(`/api/takes/${CURRENT}/open`, { app: "maya", person: personId }).catch(fail));
$("reveal").addEventListener("click", () => api(`/api/takes/${CURRENT}/open`, { app: "folder", person: personId }).catch(fail));
wireDrop($("attach-drop"), $("attach-input"), async (files) => {
  try {
    const ids = [];
    for (const f of files) ids.push((await upload(f)).id);
    const d = await api(`/api/takes/${CURRENT}/attach`, { files: ids });
    openTake(CURRENT, d.job);
  } catch (e) { fail(e); }
});

const FMT = {
  found: (v) => `${(v * 100).toFixed(0)}%`, gap: (v) => `${v.toFixed(1)} s`, out_of_frame: (v) => `${(v * 100).toFixed(1)}%`,
  size: (v) => `${(v * 100).toFixed(0)}%`, vis_arms: (v) => `${(v * 100).toFixed(0)}%`, vis_legs: (v) => `${(v * 100).toFixed(0)}%`,
  vis_head: (v) => `${(v * 100).toFixed(0)}%`, jitter: (v) => `${v.toFixed(1)} m/s²`, foot_skate: (v, it) => `${v.toFixed(0)} cm/s${it.observed_pairs ? ` · ${it.observed_pairs} pairs` : ""}`,
  reprojection: (v) => `${(v * 100).toFixed(1)}%`, upper_body: () => "",
  hand_left_coverage: (v) => `${(v * 100).toFixed(0)}%`, hand_right_coverage: (v) => `${(v * 100).toFixed(0)}%`,
};
function renderReport(rep) {
  if (!rep) { $("score").textContent = "—"; $("score").className = "score"; $("verdict").textContent = lang === "ru" ? "Проверки качества для этой анимации нет — обработайте дубль заново." : "No quality check for this animation — process the take again."; $("items").replaceChildren(); renderFinalMotion(null); return; }
  $("score").textContent = rep.score; $("score").className = "score " + rep.verdict;
  $("verdict").textContent = `${t("verdict_" + rep.verdict)} ${t("quality_scope")}`;
  const ul = $("items"); ul.replaceChildren();
  for (const it of rep.items) {
    ul.append(el("li", { class: it.level }, el("b", { text: t("r_" + it.id) }),
      el("span", { class: "val", text: (FMT[it.id] || String)(it.value, it) }),
      it.level === "limited" ? el("small", { text: t("r_foot_skate_low_evidence") }) : it.level !== "good" ? el("small", { text: t("r_" + it.id + "_adv") }) : null));
  }
  renderFinalMotion(rep.final_motion);
}

function renderFinalMotion(motion) {
  const panel = $("output-motion"), list = $("output-motion-items");
  if (!motion || motion.kind !== "post-processed-bvh") { panel.classList.add("hidden"); list.replaceChildren(); return; }
  panel.classList.remove("hidden"); list.replaceChildren();
  for (const side of ["Left", "Right"]) {
    const row = motion.contacts?.[side]; if (!row) continue;
    const sideName = lang === "ru" ? (side === "Left" ? "Левая стопа" : "Правая стопа") : `${side} foot`;
    const pct = (100 * row.coverage).toFixed(0);
    const info = row.intervals === 0 ? t("output_contact_none") : `${row.intervals} ${t("output_contact_intervals")} · ${row.contact_frames}/${motion.frames} ${t("output_contact_frames")} (${pct}%)`;
    const drift = row.max_drift_cm == null ? t("output_foot_drift_none") : `${t("output_foot_drift")}: ${row.max_drift_cm.toFixed(1)} cm · ${row.max_step_cm.toFixed(2)} cm/frame`;
    list.append(el("li", { class: row.contact_frames < 15 ? "limited" : row.max_drift_cm > 5 ? "warn" : "good" },
      el("b", { text: sideName }), el("span", { class: "val", text: info }), el("small", { text: drift })));
  }
  list.append(el("li", { class: "limited" }, el("b", { text: "" }), el("span", { text: t("output_quality_hint") })));
}
// ---------------------------------------------------------------- плеер, оверлей, полоса качества
const video = $("video");
const MP_EDGES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [27, 31],
  [24, 26], [26, 28], [28, 32], [0, 7], [0, 8], [15, 19], [16, 20]];
let selfFrame = 0, selfPlaying = false, lastTs = 0;
const fps = () => overlayData?.fps || TAKE?.fps || 30;
const frameCount = () => (overlayData?.skeleton?.length) || TAKE?.frames || 0;
function currentFrame() {
  if (TAKE?.video && video.readyState >= 1) return Math.min(frameCount() - 1, Math.max(0, Math.floor(video.currentTime * fps() + 1e-3)));
  return Math.floor(selfFrame);
}
function drawOverlay(f) {
  const c = $("overlay"), wrap = $("video-wrap");
  const W = wrap.clientWidth, H = wrap.clientHeight, dpr = devicePixelRatio || 1;
  if (c.width !== W * dpr || c.height !== H * dpr) { c.width = W * dpr; c.height = H * dpr; }
  const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  if (!overlayData || !video.videoWidth) return;
  const vw = video.videoWidth, vh = video.videoHeight;
  const s = Math.min(W / vw, H / vh), ox = (W - vw * s) / 2, oy = (H - vh * s) / 2;
  for (const participant of overlayPeople) {
  const data = participant.overlayData;
  if (!data || f < (participant.start_frame ?? 0) || f > (participant.end_frame ?? Infinity)) continue;
  if (data.detected && !data.detected[f]) continue;
  const k = vw / data.width;  // оверлей посчитан в пикселях исходника
  const P = (p) => [ox + p[0] * k * s, oy + p[1] * k * s];
  const det = data.detected?.[f];
  if (det && $("show-detected").checked) {
    g.strokeStyle = participant.color; g.lineWidth = 2;
    for (const [a, b] of MP_EDGES) { const A = P(det[a]), B = P(det[b]); g.beginPath(); g.moveTo(...A); g.lineTo(...B); g.stroke(); }
    g.fillStyle = participant.color; for (const p of det) { const [x, y] = P(p); g.fillRect(x - 2, y - 2, 4, 4); }
  }
  const sk = data.skeleton?.[f];
  if (sk && $("show-skeleton").checked) {
    g.strokeStyle = participant.color; g.lineWidth = 3; g.lineCap = "round";
    data.parents.forEach((par, j) => { if (par >= 0) { g.beginPath(); g.moveTo(...P(sk[par])); g.lineTo(...P(sk[j])); g.stroke(); } });
    g.fillStyle = "#fff"; for (const p of sk) { const [x, y] = P(p); g.beginPath(); g.arc(x, y, 2.5, 0, 7); g.fill(); }
  }
  const labelPoints = det || sk;
    const detail = data.details?.[f];
    if (detail) {
      g.strokeStyle = participant.color; g.fillStyle = participant.color; g.lineWidth = 1;
      for (const hand of ($("show-hands").checked ? Object.values(detail.hands || {}) : [])) {
        const pts = hand.image;
        for (const start of [1,5,9,13,17]) {
          g.beginPath(); g.moveTo(...P(pts[0]));
          for (let j=start;j<start+4;j++) g.lineTo(...P(pts[j]));
          g.stroke();
        }
        for (const p of pts) { const [x,y]=P(p); g.fillRect(x-1,y-1,2,2); }
      }
      if (detail.face && $("show-face").checked) for (const p of detail.face.image) {
        const [x,y]=P(p); g.fillRect(x-.5,y-.5,1,1);
      }
    }
  if (labelPoints) {
    const [x, y] = P(labelPoints[0]); g.fillStyle = participant.color; g.font = "bold 13px sans-serif";
    g.fillText(`ID ${personId === 0 ? participant.id : personId || 1}`, x+8, y-8);
  }
  }
}
function drawStrip() {
  const c = $("strip");
  const reports = personId === 0 ? (TAKE?.people || []).map((p) => p.report?.per_frame || []) : [TAKE?.report?.per_frame || []];
  const q = Array.from({ length: Math.max(0, ...reports.map((r) => r.length)) }, (_, i) => {
    const values = reports.map((r) => r[i]).filter((v) => v != null);
    return values.length ? values.reduce((a, b) => a+b, 0)/values.length : null;
  });
  c.width = c.clientWidth * (devicePixelRatio || 1); c.height = 14;
  const g = c.getContext("2d"); g.clearRect(0, 0, c.width, c.height);
  if (!q.length) { workbench.paint(c,frameCount()); return; }
  const w = c.width / q.length;
  q.forEach((v, i) => {
    g.fillStyle = v == null ? "#444" : v >= 0.75 ? "#3f8f58" : v >= 0.5 ? "#a27c4f" : "#a8524b";
    g.fillRect(i * w, 0, Math.ceil(w), 14);
  });
  workbench.paint(c,frameCount());
  // маркеры аниматора — жёлтые засечки
  g.fillStyle = "#f0ce67";
  for (const m of sceneTake?.markers || []) g.fillRect((m.frame - 1) / Math.max(1, frameCount()) * c.width, 0, 2, 14);
  const f = currentFrame();
  g.fillStyle = "#fff"; g.fillRect(f * w, 0, Math.max(2, w), 14);
}
$("strip").addEventListener("click", (e) => {
  const r = e.target.getBoundingClientRect(); const f = Math.floor((e.clientX - r.left) / r.width * frameCount());
  seekFrame(f);
});
function renderMarkers() {
  const markers = sceneTake?.markers || [];
  $("marker-list").classList.toggle("hidden", !markers.length); $("marker-del").classList.toggle("hidden", !markers.length);
  $("marker-list").replaceChildren(el("option", { value: "", text: (lang === "ru" ? "Маркеры" : "Markers") + ` (${markers.length})` }),
    ...markers.map((m, i) => el("option", { value: i, text: `${m.frame} · ${m.label || "—"}` })));
}
async function saveMarkers(markers) {
  const d = await api(`/api/takes/${CURRENT}/meta`, { markers });
  sceneTake.markers = d.markers; if (TAKE !== sceneTake) TAKE.markers = d.markers;
  renderMarkers(); drawStrip();
}
$("marker-add").addEventListener("click", async () => {
  const frame = currentFrame() + 1, label = prompt(lang === "ru" ? `Название маркера (кадр ${frame})` : `Marker name (frame ${frame})`, "");
  if (label === null) return;
  try { await saveMarkers([...(sceneTake?.markers || []), { frame, label: label.trim() }]); } catch (e) { fail(e); }
});
$("marker-list").addEventListener("change", () => { const m = (sceneTake?.markers || [])[Number($("marker-list").value)]; if (m) seekFrame(m.frame - 1); });
$("marker-del").addEventListener("click", async () => {
  const i = $("marker-list").value; if (i === "") return;
  try { await saveMarkers((sceneTake?.markers || []).filter((_, k) => k !== Number(i))); } catch (e) { fail(e); }
});
function seekFrame(f) {
  f = Math.max(0, Math.min(frameCount()-1, f));
  if (TAKE?.video) video.currentTime = (f + 0.5) / fps(); else selfFrame = f;
  syncFrame();
}
// ---------------------------------------------------------------- правка позы и опоры стоп
// Слой — как core/pose_layer.py: D = Euler XYZ (как THREE.Euler 'XYZ'), локально R' = R·D; между ключами — slerp
// со smoothstep, до первого и после последнего ключа — спад к нулю за falloff кадров.
const PE = { keys: [], pins: [], contacts: { add: {}, remove: {} }, joint: "", bvh: null, person: 1, take: "", modeBefore: null, saveTimer: 0 };
const D2R = Math.PI / 180, smooth = (t) => { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); };
function quatXYZ([x, y, z]) {
  const c1 = Math.cos(x * D2R / 2), c2 = Math.cos(y * D2R / 2), c3 = Math.cos(z * D2R / 2);
  const s1 = Math.sin(x * D2R / 2), s2 = Math.sin(y * D2R / 2), s3 = Math.sin(z * D2R / 2);
  return [c1 * c2 * c3 - s1 * s2 * s3, s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 + s1 * s2 * c3];
}
function slerpQ(a, b, t) {
  let d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
  if (d < 0) { b = b.map((v) => -v); d = -d; }
  if (d > 0.9995) { const r = a.map((v, i) => v + (b[i] - v) * t), n = Math.hypot(...r); return r.map((v) => v / n); }
  const th = Math.acos(d), sa = Math.sin((1 - t) * th) / Math.sin(th), sb = Math.sin(t * th) / Math.sin(th);
  return a.map((v, i) => v * sa + b[i] * sb);
}
const ID = [1, 0, 0, 0];
function jointKeys(keys, joint) {
  const byFrame = new Map(); for (const k of keys) if (k.joint === joint) byFrame.set(k.frame, k);  // последний на кадре — главный
  return [...byFrame.values()].sort((a, b) => a.frame - b.frame);
}
function layerDelta(keys, joint, f) {
  const ks = jointKeys(keys, joint); if (!ks.length) return null;
  const first = ks[0], last = ks[ks.length - 1];
  if (f < first.frame) return first.falloff > 0 && f >= first.frame - first.falloff ? slerpQ(ID, quatXYZ(first.rot), smooth((f - (first.frame - first.falloff)) / first.falloff)) : null;
  if (f > last.frame) return last.falloff > 0 && f <= last.frame + last.falloff ? slerpQ(quatXYZ(last.rot), ID, smooth((f - last.frame) / last.falloff)) : null;
  for (let i = 0; i < ks.length; i++) {
    if (ks[i].frame === f) return quatXYZ(ks[i].rot);
    if (ks[i + 1] && f > ks[i].frame && f < ks[i + 1].frame)
      return slerpQ(quatXYZ(ks[i].rot), quatXYZ(ks[i + 1].rot), smooth((f - ks[i].frame) / (ks[i + 1].frame - ks[i].frame)));
  }
  return null;
}
const sliderRot = () => ["x", "y", "z"].map((a) => Number($("pe-" + a).value));
function previewKeys() {  // ползунки — временный ключ на текущем кадре
  const rot = sliderRot();
  if (!PE.joint || rot.every((v) => !v)) return PE.keys;
  return [...PE.keys.filter((k) => !(k.joint === PE.joint && k.frame === currentFrame())),
    { joint: PE.joint, frame: currentFrame(), rot, falloff: Number($("pe-falloff").value) || 0 }];
}
function parseBvh(text) {
  const [head, motion] = text.split("MOTION"); const names = [], chans = [];
  const tokens = head.match(/[{}]|[^\s{}]+/g) || [];
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i] === "ROOT" || tokens[i] === "JOINT") { names.push(tokens[i + 1]); chans.push([]); }
    else if (tokens[i] === "CHANNELS") { const n = Number(tokens[i + 1]); chans[chans.length - 1] = tokens.slice(i + 2, i + 2 + n); }
  }
  const lines = motion.trim().split(/\r?\n/), at = lines.findIndex((l) => l.startsWith("Frame Time")) + 1;
  const offsets = []; let o = 0; for (const c of chans) { offsets.push(o); o += c.length; }
  return { names, chans, offsets, rows: lines.slice(at).filter((l) => l.trim()).map((l) => l.trim().split(/\s+/).map(Number)) };
}
function subtract(ranges, [a, b]) {
  const out = []; for (const [x, y] of ranges || []) { if (y < a || x > b) out.push([x, y]); else { if (x < a) out.push([x, a - 1]); if (y > b) out.push([b + 1, y]); } }
  return out;
}
function markContacts(sides, planted) {
  const r = [rangeFirst - 1, rangeLast - 1];
  for (const side of sides) {
    const keep = planted ? "add" : "remove", drop = planted ? "remove" : "add";
    PE.contacts[drop][side] = subtract(PE.contacts[drop][side], r);
    PE.contacts[keep][side] = [...subtract(PE.contacts[keep][side], r), r].sort((x, y) => x[0] - y[0]);
  }
  peChanged();
}
function peChanged() {
  renderPeKeys(); drawCurves(); viewer3d?.setLayer(peActive() ? (name, f) => layerDelta(previewKeys(), name, f) : null);
  clearTimeout(PE.saveTimer);
  PE.saveTimer = setTimeout(() => api(`/api/takes/${PE.take}/edits`, { person: PE.person, keys: PE.keys, contacts: PE.contacts, pins: PE.pins })
    .then((d) => { $("pe-state").textContent = (lang === "ru" ? `Несохранённых ключей: ${d.keys}, закреплений: ${d.pins}` : `Pending keys: ${d.keys}, pins: ${d.pins}`); }).catch(fail), 400);
}
const peActive = () => $("pose-editor").open && !$("pose-editor").classList.contains("hidden");
async function peLoad(media, tk) {
  PE.bvh = media.length === 1 ? parseBvh(media[0].text) : null;
  PE.take = tk.id; PE.person = personId || 1;
  const usable = Boolean(PE.bvh) && personId !== 0 && tk.status === "done" && !busy0(tk);
  $("pose-editor").classList.toggle("hidden", !usable);
  if (!usable) { viewer3d?.setLayer(null); return; }
  const data = await api(`/api/takes/${tk.id}/edits?person=${PE.person}`).catch(() => null);
  PE.keys = data?.keys || []; PE.pins = data?.pins || []; PE.contacts = { add: data?.contacts?.add || {}, remove: data?.contacts?.remove || {} };
  const holds = await api(`/api/takes/${tk.id}/hand-holds?person=${PE.person}`).catch(() => ({ candidates: [] }));
  renderHandCandidates(holds.candidates || []);
  const names = PE.bvh.names;
  if (!names.includes(PE.joint)) PE.joint = names.find((n) => /LeftForeArm$/.test(n)) || names[0];
  $("pe-joint").replaceChildren(...names.map((n) => el("option", { value: n, text: n })));
  $("pe-joint").value = PE.joint;
  viewer3d.setPickHandler((name) => { PE.joint = name; $("pe-joint").value = name; viewer3d.setPicked(name); peOnFrame(currentFrame()); drawCurves(); });
  $("pe-state").textContent = PE.keys.length || PE.pins.length || Object.keys(PE.contacts.add).length || Object.keys(PE.contacts.remove).length
    ? (lang === "ru" ? "Есть несохранённые правки — «Применить» запишет их в анимацию" : "Unsaved edits — “Apply” writes them into the animation") : "";
  peToggle();
}
function peToggle() {
  if (!viewer3d) return;
  const on = peActive();
  if (on && PE.modeBefore === null) { PE.modeBefore = $("surface-mode").value; $("surface-mode").value = "bones"; viewer3d.setMode("bones"); }
  if (!on && PE.modeBefore !== null) { $("surface-mode").value = PE.modeBefore; viewer3d.setMode(PE.modeBefore); PE.modeBefore = null; }
  viewer3d.setPicked(on ? PE.joint : ""); viewer3d.setLayer(on ? (name, f) => layerDelta(previewKeys(), name, f) : null);
  renderPeKeys(); drawCurves();
}
function peOnFrame(f) {
  if (!peActive() || !PE.joint) return;
  const key = PE.keys.find((k) => k.joint === PE.joint && k.frame === f);
  const rot = key ? key.rot : [0, 0, 0];
  ["x", "y", "z"].forEach((a, i) => { $("pe-" + a).value = rot[i]; $("pe-" + a + "v").textContent = `${rot[i]}°`; });
  if (key) $("pe-falloff").value = key.falloff;
  drawCurves();
}
let handCandidates = [];
function renderHandCandidates(items) {
  handCandidates = items;
  const select = $("pe-hand-candidates");
  const label = lang === "ru" ? "Подсказки кистей" : "Hand candidates";
  select.replaceChildren(el("option", { value: "", text: `${label} (${items.length})` }),
    ...items.map((c, i) => el("option", { value: i, text: `${c.side} · ${c.first + 1}–${c.last + 1} · ${c.mean_speed_cm_s} cm/s` })));
  $("pe-hand-candidate-status").textContent = items.length
    ? t("pe_hand_candidate_hint")
    : (lang === "ru" ? "Малоподвижных участков кистей не найдено. Закрепление можно добавить вручную выше." : "No low-motion wrist intervals found. You can add a hand pin manually above.");
}
$("pe-hand-candidate-use").addEventListener("click", () => {
  const c = handCandidates[Number($("pe-hand-candidates").value)];
  if (!c) return;
  $("clip-in").value = c.first + 1; $("clip-out").value = c.last + 1;
  if (!changeRange(true)) return;
  $("pe-pin-effector").value = c.effector;
  PE.pins = [...PE.pins, { effector: c.effector, first: c.first, last: c.last, blend: 0.15 }];
  peChanged(); seekFrame(c.first);
  $("pe-hand-candidate-status").textContent = lang === "ru"
    ? "Черновик закрепления добавлен. Проверьте видео и 3D, затем нажмите «Применить правки»."
    : "Hand pin draft added. Review the video and 3D, then click “Apply edits”.";
});
function renderPePins() {
  const names = { LeftHand: t("pin_lh"), RightHand: t("pin_rh"), LeftFoot: t("pin_lf"), RightFoot: t("pin_rf") };
  $("pe-pins").replaceChildren(el("option", { value: "", text: (lang === "ru" ? "Закрепления" : "Pins") + ` (${PE.pins.length})` }),
    ...PE.pins.map((p, i) => el("option", { value: i, text: `${names[p.effector]} · ${p.first + 1}–${p.last + 1}` })));
}
function renderPeKeys() {
  renderPePins();
  const keys = PE.keys.map((k, i) => ({ k, i })).sort((a, b) => a.k.frame - b.k.frame);
  $("pe-keys").replaceChildren(el("option", { value: "", text: (lang === "ru" ? "Ключи" : "Keys") + ` (${PE.keys.length})` }),
    ...keys.map(({ k, i }) => el("option", { value: i, text: `${k.frame + 1} · ${k.joint.split(":").pop()} · ${k.rot.map((v) => Math.round(v)).join("/")}` })));
}
function drawCurves() {
  const c = $("pe-curves"); if (!peActive() || !PE.bvh) return;
  c.width = c.clientWidth * (devicePixelRatio || 1); c.height = 130 * (devicePixelRatio || 1);
  const g = c.getContext("2d"), W = c.width, H = c.height, rows = PE.bvh.rows, n = rows.length, plotH = H - 26 * (devicePixelRatio || 1);
  g.clearRect(0, 0, W, H); g.fillStyle = "#16181b"; g.fillRect(0, 0, W, plotH);
  const j = PE.bvh.names.indexOf(PE.joint);
  if (j >= 0 && n) {
    const ch = PE.bvh.chans[j], off = PE.bvh.offsets[j];
    [["Zrotation", "#5c9be2"], ["Xrotation", "#e27870"], ["Yrotation", "#9cce72"]].forEach(([name, color]) => {
      const k = ch.indexOf(name); if (k < 0) return;
      g.strokeStyle = color; g.lineWidth = 1.5; g.beginPath();
      rows.forEach((r, f) => { const x = f / Math.max(1, n - 1) * W, y = plotH / 2 - r[off + k] / 180 * (plotH / 2 - 4); f ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.stroke();
    });
    g.fillStyle = "#f0ce67";
    for (const key of PE.keys) if (key.joint === PE.joint) g.fillRect(key.frame / Math.max(1, n - 1) * W - 1, 0, 3, plotH);
  }
  const rowH = (H - plotH) / 2;
  ["Left", "Right"].forEach((side, i) => {
    const y = plotH + i * rowH;
    g.fillStyle = "#23262a"; g.fillRect(0, y + 1, W, rowH - 2);
    for (const [op, color] of [["add", "#5cc97b"], ["remove", "#e27870"]])
      for (const [a, b] of PE.contacts[op][side] || []) { g.fillStyle = color; g.fillRect(a / Math.max(1, n - 1) * W, y + 1, Math.max(2, (b - a + 1) / Math.max(1, n - 1) * W), rowH - 2); }
    g.fillStyle = "#a2a4a8"; g.font = `${10 * (devicePixelRatio || 1)}px sans-serif`; g.fillText(i ? (lang === "ru" ? "П" : "R") : (lang === "ru" ? "Л" : "L"), 3, y + rowH - 4);
  });
  g.fillStyle = "#fff"; g.fillRect(currentFrame() / Math.max(1, n - 1) * W, 0, 2, H);
}
$("pose-editor").addEventListener("toggle", peToggle);
$("pe-joint").addEventListener("change", () => { PE.joint = $("pe-joint").value; viewer3d?.setPicked(PE.joint); peOnFrame(currentFrame()); });
for (const a of ["x", "y", "z"]) $("pe-" + a).addEventListener("input", () => {
  $("pe-" + a + "v").textContent = `${$("pe-" + a).value}°`;
  viewer3d?.setLayer((name, f) => layerDelta(previewKeys(), name, f));
});
$("pe-key").addEventListener("click", () => {
  if (!PE.joint) return;
  const f = currentFrame();
  PE.keys = [...PE.keys.filter((k) => !(k.joint === PE.joint && k.frame === f)), { joint: PE.joint, frame: f, rot: sliderRot(), falloff: Number($("pe-falloff").value) || 0 }];
  peChanged();
});
$("pe-zero").addEventListener("click", () => { ["x", "y", "z"].forEach((a) => { $("pe-" + a).value = 0; $("pe-" + a + "v").textContent = "0°"; }); peChanged(); });
$("pe-keys").addEventListener("change", () => { const k = PE.keys[Number($("pe-keys").value)]; if (k) { PE.joint = k.joint; $("pe-joint").value = k.joint; viewer3d?.setPicked(k.joint); seekFrame(k.frame); } });
$("pe-key-del").addEventListener("click", () => { const i = $("pe-keys").value; if (i === "") return; PE.keys = PE.keys.filter((_, k) => k !== Number(i)); peChanged(); });
$("pe-contact-l").addEventListener("click", () => { if (changeRange()) markContacts(["Left"], true); });
$("pe-contact-r").addEventListener("click", () => { if (changeRange()) markContacts(["Right"], true); });
$("pe-contact-free").addEventListener("click", () => { if (changeRange()) markContacts(["Left", "Right"], false); });
$("pe-discard").addEventListener("click", () => { if (!confirm(lang === "ru" ? "Отменить все несохранённые правки позы и опор?" : "Discard all unsaved pose and contact edits?")) return;
  PE.keys = []; PE.pins = []; PE.contacts = { add: {}, remove: {} }; peChanged(); peOnFrame(currentFrame()); });
$("pe-pin").addEventListener("click", () => {
  if (!changeRange()) return;
  PE.pins = [...PE.pins, { effector: $("pe-pin-effector").value, first: rangeFirst - 1, last: rangeLast - 1, blend: 0.15 }];
  peChanged();
});
$("pe-pins").addEventListener("change", () => { const p = PE.pins[Number($("pe-pins").value)]; if (p) seekFrame(p.first); });
$("pe-pin-del").addEventListener("click", () => { const i = $("pe-pins").value; if (i === "") return; PE.pins = PE.pins.filter((_, k) => k !== Number(i)); peChanged(); });
$("pe-apply").addEventListener("click", async () => {
  clearTimeout(PE.saveTimer);
  try {
    await api(`/api/takes/${PE.take}/edits`, { person: PE.person, keys: PE.keys, contacts: PE.contacts, pins: PE.pins });
    const d = await api(`/api/takes/${CURRENT}/bake`, { person: personId || null });
    viewer3d?.setLayer(null); openTake(CURRENT, d.job);
  } catch (e) { fail(e); }
});
$("pe-curves").addEventListener("click", (e) => { const r = e.target.getBoundingClientRect(); seekFrame(Math.round((e.clientX - r.left) / r.width * Math.max(0, frameCount() - 1))); });
$("onion").addEventListener("change", () => viewer3d?.setOnion(Number($("onion").value)));
// раскладка: видео и 3D рядом (и на узком окне), крупный 3D или крупное видео; запоминается в браузере
function applyLayout() {
  const v = $("view-layout").value;
  for (const c of ["layout-side", "layout-big3d", "layout-bigvideo"]) $("t-viewer").classList.toggle(c, v && c === "layout-" + v);
  try { localStorage.setItem("mocapgate-layout", v); } catch {}
  setTimeout(() => { if (!TAKE) return; viewer3d?.resize(); syncFrame(); }, 50);
}
try { $("view-layout").value = localStorage.getItem("mocapgate-layout") || ""; } catch {}
$("view-layout").addEventListener("change", applyLayout);
applyLayout();
function syncFrame() {
  const f = currentFrame(), n = frameCount();
  drawOverlay(f); drawStrip();
  peOnFrame(f);
  viewer3d?.setFrame(f);
  workbench.sync(f,fps());
  $("seek").value = n ? Math.round(f / Math.max(1, n - 1) * 1000) : 0;
  $("time").textContent = `${f + 1} / ${n}`;
}
$("seek").addEventListener("input", (e) => seekFrame(Math.round(e.target.value / 1000 * Math.max(0, frameCount() - 1))));
$("play").addEventListener("click", () => {
  if (TAKE?.video) { if (video.paused) { if (currentFrame() < rangeFirst-1 || currentFrame() >= rangeLast-1) seekFrame(rangeFirst-1); video.play().catch(fail); } else video.pause(); }
  else { selfPlaying = !selfPlaying; if (selfPlaying && (currentFrame()<rangeFirst-1 || currentFrame()>=rangeLast-1)) selfFrame=rangeFirst-1; lastTs = 0; }
  $("play").textContent = (TAKE?.video ? !video.paused : selfPlaying) ? "❚❚" : "▶";
});
video.addEventListener("pause", () => { $("play").textContent = "▶"; });
video.addEventListener("play", () => { $("play").textContent = "❚❚"; });
video.addEventListener("error", () => {
  if (!TAKE?.video) return;
  const code = video.error?.code;
  const detail = code === 4 ? (lang === "ru" ? "Формат или кодек видео не поддерживается этим окном." : "This window does not support the video's format or codec.")
    : code === 2 ? (lang === "ru" ? "Не удалось загрузить видео. Проверьте локальный файл и повторите." : "The video could not be loaded. Check the local file and retry.")
    : (lang === "ru" ? "Не удалось декодировать видео. Повторите загрузку дубля." : "The video could not be decoded. Reload the take to retry.");
  const box = $("media-error");
  box.textContent = `${detail} (${code ?? "?"})`;
  box.classList.remove("hidden");
});
$("speed").addEventListener("change", (e) => { video.playbackRate = Number(e.target.value); });
["show-detected", "show-skeleton", "show-hands", "show-face"].forEach((id) => $(id).addEventListener("change", syncFrame));
video.addEventListener("seeked", syncFrame);
video.addEventListener("loadedmetadata", syncFrame);
function loop(ts) {
  if (view === "takes" && TAKE) {
    if (!TAKE.video && selfPlaying && frameCount()) {
      if (lastTs) selfFrame += (ts-lastTs)/1000*fps()*Number($("speed").value);
      if (selfFrame>=rangeLast) { if (loopEnabled()) selfFrame=rangeFirst-1+(selfFrame-rangeFirst+1)%(rangeLast-rangeFirst+1); else { selfFrame=rangeLast-1; selfPlaying=false; $("play").textContent="▶"; } }
      lastTs = ts; syncFrame();
    } else if (TAKE.video && !video.paused) {
      if (video.currentTime>=rangeLast/fps()) { if (loopEnabled()) seekFrame(rangeFirst-1); else { video.pause(); seekFrame(rangeLast-1); } }
      syncFrame();
    }
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
video.addEventListener("ended", () => { if (loopEnabled()) { seekFrame(rangeFirst-1); video.play().catch(fail); } });
function loopEnabled() { return $("clip-loop").getAttribute("aria-pressed")==="true"; }
$("clip-loop").addEventListener("click",()=>$("clip-loop").setAttribute("aria-pressed",String(!loopEnabled())));
let rangeFirst=1, rangeLast=1, rangeKey="";
function resetRange(force=false) {
  const key=`${CURRENT}/${personId}/${TAKE?.fps}/${TAKE?.frames}`;
  if (force || key!==rangeKey) { rangeFirst=1;rangeLast=Math.max(1,frameCount());rangeKey=key; }
  $("clip-in").max=$("clip-out").max=String(Math.max(1,frameCount()));
  $("clip-in").value=rangeFirst;$("clip-out").value=rangeLast;
  $("clip-duration").textContent=`${rangeFirst}–${rangeLast} · ${framesText(rangeLast-rangeFirst+1)} · ${((rangeLast-rangeFirst+1)/fps()).toFixed(3)} ${lang==="ru"?"с":"s"}`;
}
function changeRange(silent=false) {
  const first=Number($("clip-in").value), last=Number($("clip-out").value);
  if (!Number.isInteger(first)||!Number.isInteger(last)||first<1||last<first||last>frameCount()) {
    $("clip-duration").textContent=lang==="ru"?"Укажите целые кадры: начало ≤ конец ≤ длина дубля":"Use integer frames: In ≤ Out ≤ frame count";
    $("export-clip").disabled=true;
    if(!silent) toast($("clip-duration").textContent);
    return false;
  }
  rangeFirst=first;rangeLast=last;
  $("clip-duration").textContent=`${first}–${last} · ${framesText(last-first+1)} · ${((last-first+1)/fps()).toFixed(3)} ${lang==="ru"?"с":"s"}`;
  $("export-clip").disabled=Boolean(TAKE?.job)||!TAKE?.bvh||personId===0;
  return true;
}
for (const id of ["clip-in","clip-out"]) {
  $(id).addEventListener("input",()=>changeRange(true));
  $(id).addEventListener("change",()=>changeRange());
}
$("mark-in").addEventListener("click",()=>{ $("clip-in").value=currentFrame()+1; changeRange(); });
$("mark-out").addEventListener("click",()=>{ $("clip-out").value=currentFrame()+1; changeRange(); });
$("clip-reset").addEventListener("click",()=>{resetRange(true);changeRange(true);});
function stepFrame(delta) { video.pause();selfPlaying=false;$("play").textContent="▶";seekFrame(currentFrame()+delta); }
$("prev-frame").addEventListener("click",()=>stepFrame(-1));
$("next-frame").addEventListener("click",()=>stepFrame(1));
// клавиши плеера на странице дубля; не мешают вводу в полях
document.addEventListener("keydown", (e) => {
  if (view !== "takes" || $("take-panel").classList.contains("hidden") || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.closest?.("input, select, textarea, [contenteditable]") || document.querySelector(".transport")?.classList.contains("hidden")) return;
  const press = { m: "marker-add", M: "marker-add", "ь": "marker-add", "Ь": "marker-add", " ": "play", ArrowLeft: "prev-frame", ArrowRight: "next-frame", i: "mark-in", I: "mark-in", o: "mark-out", O: "mark-out", "ш": "mark-in", "Ш": "mark-in", "щ": "mark-out", "Щ": "mark-out" }[e.key];
  if (!press || $(press).disabled) return;
  if (e.target.closest?.("button") && e.key === " ") return;  // пробел на кнопке — её собственное нажатие
  e.preventDefault(); $(press).click();
});
$("export-clip").addEventListener("click",async()=>{ if(!changeRange()) return; try {
  const result=await api(`/api/takes/${CURRENT}/clip`,{first:rangeFirst,last:rangeLast,person:personId,inplace:$("clip-inplace").checked,fbx:$("clip-fbx").checked,
    loop:$("clip-make-loop").checked,root_motion:$("clip-root-motion").checked,
    edit:{mirror:$("ce-mirror").checked,floor:$("ce-floor").checked,speed:Number($("ce-speed").value)||1,yaw:Number($("ce-yaw").value)||0,
      scale:Number($("ce-scale").value)||1,ease_in:Number($("ce-ease-in").value)||0,ease_out:Number($("ce-ease-out").value)||0}});
  openTake(CURRENT,result.job);
} catch(e) {fail(e);} });
// исправить участок: кадры In–Out заменяются плавной интерполяцией соседних (прежняя версия — в истории)
$("repair-range").addEventListener("click",async()=>{ if(!changeRange()) return;
  if(!confirm(t("repair_confirm").replace("{a}",rangeFirst).replace("{b}",rangeLast))) return;
  try { const d=await api(`/api/takes/${CURRENT}/repair`,{first:rangeFirst,last:rangeLast,person:personId||null}); openTake(CURRENT,d.job); } catch(e) {fail(e);} });

// ---------------------------------------------------------------- движки и свой персонаж
function fileLink(tk, kind, file, label) {
  return el("a", { class: "button small", text: label, href: withT(`/files/${tk.id}/${encodeURIComponent(file)}?download=1`), onclick: (e) => {
    if (TAKE?.job || TAKE?.status === "processing") { e.preventDefault(); return; }
    if (!STATUS?.desktop) return;
    e.preventDefault(); api(`/api/takes/${CURRENT}/save`, { kind, person: personId || null, archive: file }).then((d) => toast(t("saved_to") + d.path)).catch(fail);
  } });
}
function renderEngines(tk) {
  const busy = Boolean(tk.job) || tk.status === "processing";
  const many = (sceneTake?.people?.length || 0) > 1;
  $("eng-all-wrap").classList.toggle("hidden", !many);
  if (renderEngines.person !== personId) $("eng-all").checked = personId === 0 && many;  // при смене участника — по умолчанию
  renderEngines.person = personId;
  const none = personId === 0 && !$("eng-all").checked;
  for (const id of ["eng-unreal", "eng-unity", "eng-gltf", "eng-mixamo", "eng-cascadeur", "eng-blend"]) $(id).disabled = busy || none || !STATUS.components.blender.path;
  $("eng-livelink").classList.toggle("hidden", !tk.face_file || personId === 0);
  $("eng-livelink").disabled = busy;
  const files = personId === 0 ? sceneTake?.engine || {} : tk.engine || {};
  const labels = { unreal: "Unreal FBX", unity: "Unity FBX", gltf: "GLB", fbx: "FBX", livelink: "Live Link Face CSV", mixamo: "Mixamo FBX", cascadeur: "Cascadeur FBX", blend: "Blender .blend" };
  $("engine-files").replaceChildren(...Object.entries(files).filter(([k]) => personId === 0 ? k.endsWith("_all") : !k.endsWith("_all"))
    .map(([k, f]) => fileLink(tk, "engine", f, `${t("download")} ${labels[k.replace("_all", "")] || k}${k.endsWith("_all") ? " · " + allPeopleText() : ""}`)));
  $("char-run").disabled = busy || personId === 0 || !$("char-select").value || !STATUS.components.blender.path;
  $("char-files").replaceChildren(...Object.entries(personId ? tk.retargeted || {} : {}).map(([c, f]) => fileLink(tk, "retargeted", f, `${t("download")} · ${c}`)));
  $("repair-range").disabled = busy || personId === 0 || !tk.bvh;
}
async function refreshCharacters(select) {
  const list = await api("/api/characters");
  $("char-select").replaceChildren(...(list.length ? list.map((c) => el("option", { value: c.name, text: c.name })) : [el("option", { value: "", text: t("char_none") })]));
  if (select && list.some((c) => c.name === select)) $("char-select").value = select;
  if (TAKE?.status === "done") renderEngines(TAKE);
}
async function runTool(action, body) {
  try { const d = await api(`/api/takes/${CURRENT}/${action}`, { person: personId || null, ...body }); openTake(CURRENT, d.job); } catch (e) { fail(e); }
}
for (const preset of ["unreal", "unity", "gltf", "livelink", "mixamo", "cascadeur", "blend"])
  $("eng-" + preset).addEventListener("click", () => runTool("engine", { preset, root_motion: $("eng-root-motion").checked, all: preset !== "livelink" && (personId === 0 || $("eng-all").checked) }));
$("eng-all").addEventListener("change", () => TAKE && renderEngines(TAKE));
$("char-select").addEventListener("change", () => TAKE && renderEngines(TAKE));
$("char-run").addEventListener("click", () => runTool("retarget", { character: $("char-select").value }));
$("char-upload").parentElement.tabIndex = 0;
$("char-upload").parentElement.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("char-upload").click(); } });
$("char-upload").addEventListener("change", async (e) => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  try { const u = await upload(f); const added = await api("/api/characters", { upload: u.id, name: f.name }); await refreshCharacters(added.name); toast(t("char_added")); } catch (er) { fail(er); }
});
function versionDate(name) {
  const iso=name.replace(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})-.*/,"$1-$2-$3T$4:$5:$6Z");
  const date=new Date(iso);
  return Number.isNaN(date.getTime())?name:date.toLocaleString(lang==="ru"?"ru-RU":"en-GB");
}
function updateClipLink() {
  const archive=$("clip-history").value;
  $("dl-clip").classList.toggle("hidden", !archive || personId===0);
  if(archive) $("dl-clip").href=withT(`/files/${CURRENT}/${encodeURIComponent(archive)}?download=1`);
}
$("clip-history").addEventListener("change",updateClipLink);
$("dl-clip").addEventListener("click",e=>{ if(TAKE?.job||personId===0){e.preventDefault();return;} if(STATUS?.desktop){e.preventDefault();api(`/api/takes/${CURRENT}/save`,{kind:"clip_archive",person:personId,archive:$("clip-history").value}).then(d=>toast(t("saved_to")+d.path)).catch(fail);} });
addEventListener("resize", () => { syncFrame(); viewer3d?.resize(); });

// ---------------------------------------------------------------- задачи
const watching = new Map();
function watchJob(id, box, bar, text, onDone) {
  if (watching.has(id)) return;
  watching.set(id, true);
  const watchedTake = box.id === "job" ? CURRENT : null;
  if (watchedTake && TAKE) { TAKE.job = id; renderTake(); }
  box.classList.remove("hidden"); bar.parentElement.classList.add("indeterminate"); bar.style.width = "0";
  if (box.id === "setup-job") box.dataset.state = "running";
  let since = 0, stage = "", started = Date.now();
  text.textContent = lang === "ru" ? "Подготовка задачи…" : "Preparing…";
  const setupBox = box.id === "setup-job";
  const detail = box.id === "job" ? $("job-detail") : setupBox ? $("setup-detail") : null;
  if (setupBox) $("setup-console").scrollIntoView({ block: "nearest", behavior: "smooth" });  // консоль рядом с кнопками мастера
  // список шагов: «✓ Подготовка видео · ● Поиск людей 93% · …» — видно, что сейчас идёт и что уже сделано
  const stepsBox = box.id === "job" ? $("job-steps") : setupBox ? $("setup-steps") : null;
  const steps = [];
  const renderSteps = (state) => {
    if (!stepsBox) return;
    stepsBox.classList.toggle("hidden", !steps.length);
    stepsBox.replaceChildren(...steps.map((s, i) => {
      const last = i === steps.length - 1;
      const cls = !last || state === "done" ? "done" : state === "failed" ? "failed" : "current";
      return el("li", { class: cls }, el("span", { text: s.label }),
        cls === "current" && s.pct != null ? el("span", { class: "pct", text: `${Math.round(s.pct * 100)}%` }) : null);
    }));
  };
  const noteStep = (ln) => {
    const label = ln.step || stages[ln.stage];
    if (!label || ln.stage === "log" || ln.stage === "done" || ln.stage === "error") return;
    if (steps[steps.length - 1]?.label !== label) steps.push({ label, pct: null, t0: Date.now() });
    if (typeof ln.progress === "number") steps[steps.length - 1].pct = ln.progress;
  };
  const stages = lang === "ru" ? {video:"Подготовка видео",setup:"Загрузка компонентов",pose:"Распознавание позы (MediaPipe)",retarget:"Повороты суставов",cleanup:"Фиксация стоп",check:"Проверка качества",smplx:"Модель SMPL-X",mesh:"Поверхность SMPL-X",gemx:"Распознавание GEM-X",gvhmr:"Распознавание GVHMR",details:"Кисти и лицо",animation:"Создание анимации",bvh:"Скелет и проверка",export:"Сохранение анимации",fbx:"Экспорт FBX",history:"Сохранение предыдущей версии",clip:"Экспорт участка",character:"Анимация персонажа"} : {video:"Preparing video",setup:"Loading components",pose:"Pose recognition (MediaPipe)",retarget:"Joint rotations",cleanup:"Foot locking",check:"Quality check",smplx:"SMPL-X model",mesh:"SMPL-X surface",gemx:"GEM-X recognition",gvhmr:"GVHMR recognition",details:"Hands and face",animation:"Creating animation",bvh:"Skeleton and checks",export:"Saving animation",fbx:"FBX export",history:"Saving previous version",clip:"Exporting clip",character:"Character animation"};
  const cancel = box.querySelector("button");
  if (cancel) cancel.classList.remove("hidden");
  if (cancel) cancel.onclick = () => api(`/api/jobs/${id}/cancel`, {}).catch(fail);
  const log = box.id === "setup-job" ? $("setup-log") : null;
  if (log) { log.textContent = ""; log.classList.remove("hidden"); }
  const resBox = box.id === "job" ? $("job-resources") : setupBox ? $("setup-resources") : null;
  let resAt = 0;
  const showResources = async () => {  // видеопамять и ОЗУ — видно, хватает ли (и что тесно)
    if (!resBox || Date.now() - resAt < 3000) return; resAt = Date.now();
    const r = await api("/api/resources").catch(() => null); if (!r) return;
    const gb = (mb) => (mb / 1024).toFixed(1), g = (r.gpu || [])[0];
    const ram = r.wsl_ram_total_mb ? [r.wsl_ram_used_mb, r.wsl_ram_total_mb, "WSL"] : [r.ram_used_mb, r.ram_total_mb, ""];
    resBox.textContent = [g && g.vram_total_mb ? `${lang === "ru" ? "Видеопамять" : "VRAM"} ${gb(g.vram_used_mb)}/${gb(g.vram_total_mb)} ${lang === "ru" ? "ГБ" : "GB"}${g.util != null ? ` · GPU ${g.util}%` : ""}` : "",
      ram[1] ? `${lang === "ru" ? "ОЗУ" : "RAM"} ${ram[2]} ${gb(ram[0])}/${gb(ram[1])} ${lang === "ru" ? "ГБ" : "GB"}` : ""].filter(Boolean).join(" · ");
    resBox.classList.toggle("warn", (g && g.vram_used_mb / g.vram_total_mb > 0.92) || (ram[1] && ram[0] / ram[1] > 0.92));
  };
  const tick = async () => {
    if (watchedTake && CURRENT !== watchedTake) { watching.delete(id); return; }
    showResources();
    try {
      const j = await api(`/api/jobs/${id}?since=${since}`);
      if (watchedTake && CURRENT !== watchedTake) { watching.delete(id); return; }
      since = j.next;
      if (watchedTake) {
        $("model-loading").classList.toggle("hidden", j.name !== "process" || j.done);
        $("three").setAttribute("aria-busy", String(j.name === "process" && !j.done));
      }
      for (const ln of j.lines) {
        if (ln.stage && ln.stage !== "log") stage = ln.stage;
        noteStep(ln);
        if (ln.message) text.textContent = ln.stage === "error" ? errorText(ln.message) : ln.message;
        if (typeof ln.progress === "number") { bar.parentElement.classList.remove("indeterminate"); bar.style.width = `${Math.round(ln.progress * 100)}%`; }
        const dl = setupBox && /(\d+) MB \/ (\d+) MB/.exec(ln.message || "");  // загрузка: процент по мегабайтам
        if (dl && Number(dl[2]) > 0) { bar.parentElement.classList.remove("indeterminate"); bar.style.width = `${Math.min(100, Math.round(dl[1] / dl[2] * 100))}%`; }
        if (log && ln.message) log.textContent += ln.message + "\n";
      }
      if (detail) {
        const seconds = Math.floor((Date.now() - started) / 1000);
        const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2,"0")}`;
        const clock = mmss(seconds);
        // оставшееся время текущего шага — по его скорости, когда пройдено хотя бы 5 %
        const cur = steps[steps.length - 1];
        const left = cur?.pct > 0.05 && cur.pct < 1 ? (Date.now() - cur.t0) / 1000 * (1 - cur.pct) / cur.pct : null;
        detail.textContent = (lang === "ru" ? `Шаг ${Math.max(1, steps.length)} · прошло ${clock}` : `Step ${Math.max(1, steps.length)} · ${clock} elapsed`)
          + (left != null ? (lang === "ru" ? ` · осталось ~${mmss(left)}` : ` · ~${mmss(left)} left`) : "")
          + (seconds > 20 && steps.length <= 2 ? (lang === "ru" ? " · первый запуск загружает модели — это дольше" : " · the first run loads the models — slower") : "");
        renderSteps(j.done ? (j.code === 0 ? "done" : "failed") : "running");
      }
      if (j.done) {
        watching.delete(id);
        if (cancel && log) cancel.classList.add("hidden");
        if (log) box.dataset.state = j.code === 2 ? "pending" : j.code === 0 ? "done" : j.cancelled ? "cancelled" : "failed";
        if (!log) box.classList.add("hidden");
        if (stepsBox) setTimeout(() => stepsBox.classList.add("hidden"), j.code === 0 ? 1500 : 0);
        bar.parentElement.classList.remove("indeterminate");
        if (j.code === 0) bar.style.width = "100%";
        if (j.code !== 0 && j.code !== 2 && !j.cancelled) toast(text.textContent || "error", true);
        if (log) showAdvice($("setup-advice"), j.code !== 0 && j.code !== 2 && !j.cancelled ? log.textContent.slice(-20000) : "");
        await loadTakes().catch(() => {});
        onDone?.(j);
        return;
      }
    } catch (e) {
      watching.delete(id); bar.parentElement.classList.remove("indeterminate");
      if (!log) { box.classList.add("hidden"); $("model-loading").classList.add("hidden"); if (TAKE) { TAKE.job = null; renderTake(); } }
      fail(e); return;
    }
    setTimeout(tick, 500);
  };
  tick();
}

let setupRunning = false;
async function startSetup(component, options = {}) {
  if (setupRunning) return;
  setupRunning = true;
  renderStatus();
  try {
    const d = await api('/api/setup', {component, model:STATUS.settings.pose_model, ...options});
    watchJob(d.job,$('setup-job'),$('setup-bar'),$('setup-text'),async () => {
      setupRunning = false;
      await loadStatus(true); renderAll();
    });
    $("setup-advice").classList.add("hidden");
  } catch (error) { setupRunning = false; renderStatus(); fail(error); }
}
$('setup-recommended').onclick = () => startSetup('recommended');

// ---------------------------------------------------------------- мастер установки
let PREFLIGHT = null, installQueue = null;
const L = (o) => (o && (o[lang] || o.ru || o.en)) || "";
function fixButton(fix) {
  if (!fix) return null;
  const label = L(fix.label) || (lang === "ru" ? "Исправить" : "Fix");
  if (fix.kind === "command") {
    return el("div", { class: "fix-command" }, el("code", { text: fix.value }),
      el("button", { class: "small ghost", text: lang === "ru" ? "Копировать" : "Copy", onclick: () => navigator.clipboard?.writeText(fix.value).then(() => toast(lang === "ru" ? "Команда скопирована" : "Command copied")) }),
      el("small", { text: label }));
  }
  if (fix.kind === "link") return el("button", { class: "small ghost", text: label, onclick: () => openUrl(fix.value) });
  if (fix.kind === "tip") return el("small", { class: "tip", text: label + (fix.value ? `: ${fix.value}` : "") });
  if (fix.value === "settings") return el("button", { class: "small", text: label, onclick: () => showView("settings") });
  if (fix.value === "retry") return el("small", { class: "tip", text: label || (lang === "ru" ? "Нажмите установку ещё раз — загрузка продолжится" : "Press install again — the download resumes") });
  if (fix.value === "wslconfig" || fix.value?.memory_gb) return el("button", { class: "small", text: label, onclick: () => applyWslConfig(fix) });
  if (typeof fix.value === "string" && /^(recommended|ffmpeg|blender|wsl|gemx|gvhmr|smplx|mediapipe)$/.test(fix.value))
    return el("button", { class: "small", text: label, onclick: () => startSetup(fix.value, fix.value === "gvhmr" ? { accept_model_terms: $("install-terms").checked } : {}) });
  return el("small", { text: label });
}
async function applyWslConfig(fix) {
  const memory = Number(fix.params?.memory_gb || fix.memory_gb || fix.value?.memory_gb || 16), swap = Number(fix.params?.swap_gb ?? fix.swap_gb ?? 8);
  if (!confirm(lang === "ru" ? `Записать в %UserProfile%\\.wslconfig: память WSL ${memory} ГБ, подкачка ${swap} ГБ? Прежний файл сохранится как .wslconfig.mocapgate-backup; WSL будет перезапущен.`
    : `Write %UserProfile%\\.wslconfig: WSL memory ${memory} GB, swap ${swap} GB? The previous file is kept as .wslconfig.mocapgate-backup; WSL restarts.`)) return;
  try { const d = await api("/api/wslconfig", { memory_gb: Math.round(memory), swap_gb: Math.round(swap) }); toast(t("saved_to") + d.path); runPreflight(); } catch (e) { fail(e); }
}
function renderPreflight() {
  const box = $("pf-results");
  if (!PREFLIGHT) { box.replaceChildren(); return; }
  const icon = { ok: "✓", warn: "!", fail: "✗", info: "·" };
  const row = (c) => el("div", { class: "pf-row " + c.level }, el("span", { class: "pf-icon", text: icon[c.level] || "·" }),
    el("div", {}, el("b", { text: L(c.title) }), c.detail ? el("small", { text: L(c.detail) }) : null, c.level === "warn" || c.level === "fail" ? fixButton(c.fix) : null));
  const problems = PREFLIGHT.checks.filter((c) => c.level === "fail" || c.level === "warn");
  const rest = PREFLIGHT.checks.filter((c) => !problems.includes(c));
  const fails = problems.filter((c) => c.level === "fail").length;
  box.replaceChildren(
    el("p", { class: fails ? "pf-summary bad" : problems.length ? "pf-summary warn" : "pf-summary good",
      text: fails ? (lang === "ru" ? `Нужно исправить: ${fails}. Остальное — предупреждения.` : `${fails} to fix; the rest are warnings.`)
        : problems.length ? (lang === "ru" ? "Можно устанавливать; есть рекомендации." : "Ready to install; see the recommendations.")
        : (lang === "ru" ? "Компьютер готов к установке." : "The computer is ready.") }),
    ...problems.map(row),
    rest.length ? el("details", {}, el("summary", { text: (lang === "ru" ? "Всё проверенное" : "Everything checked") + ` (${rest.length})` }), ...rest.map(row)) : null,
    PREFLIGHT.recommend?.reason ? el("p", { class: "hint", text: (lang === "ru" ? "Рекомендуем: " : "Recommended: ") + L(PREFLIGHT.recommend.reason) }) : null);
  renderInstallPlan();
}
async function runPreflight() {
  $("pf-run").disabled = true; $("pf-results").textContent = lang === "ru" ? "Проверяю компьютер (до 45 с)…" : "Checking the computer (up to 45 s)…";
  try { PREFLIGHT = await api("/api/preflight", { network: runPreflight.manual === true }); renderPreflight(); } catch (e) { $("pf-results").textContent = ""; fail(e); } finally { $("pf-run").disabled = false; }
}
// что поставить по кнопке «всё рекомендуемое»: только недостающее, в правильном порядке
function installPlan() {
  const c = STATUS.components, plan = [];
  if (!c.ffmpeg.path || !c.blender.path) plan.push("recommended");
  const models = (PREFLIGHT?.recommend?.models || []).filter((m) => m === "gemx" || m === "gvhmr");
  const windows = c.platform.system === "Windows";
  const wslBroken = (PREFLIGHT?.checks || []).some((k) => /^wsl/.test(k.id) && k.level === "fail" && (k.fix?.value === "wsl" || /install|установ/i.test(L(k.fix?.label))));
  if (windows && models.length && wslBroken) plan.push("wsl");
  if (models.includes("gemx") && !c.gemx?.ready) plan.push("gemx");
  if (models.includes("gvhmr") && !c.gvhmr_local.ready) plan.push("gvhmr");
  return plan;
}
const PLAN_NAMES = { recommended: ["FFmpeg и Blender", "FFmpeg and Blender"], wsl: ["WSL2 и Ubuntu", "WSL2 and Ubuntu"], gemx: ["GEM-X", "GEM-X"], gvhmr: ["GVHMR", "GVHMR"] };
function renderInstallPlan() {
  if (!STATUS) return;
  const plan = installPlan();
  $("install-terms-wrap").classList.toggle("hidden", !plan.includes("gvhmr"));
  $("install-plan").textContent = !PREFLIGHT ? (lang === "ru" ? "Сначала проверьте компьютер — по результату будет понятно, что ставить." : "Check the computer first — it decides what to install.")
    : plan.length ? (lang === "ru" ? "Будет установлено: " : "Will install: ") + plan.map((k) => PLAN_NAMES[k][lang === "ru" ? 0 : 1]).join(" → ")
    : (lang === "ru" ? "Всё рекомендуемое уже установлено." : "Everything recommended is installed.")
      + (PREFLIGHT.recommend?.models?.includes("gvhmr-colab") ? (lang === "ru" ? " Без NVIDIA используйте GVHMR · Colab." : " Without NVIDIA use GVHMR · Colab.") : "");
  $("install-all").disabled = setupRunning || installQueue !== null || !PREFLIGHT || !plan.length || (PREFLIGHT.checks || []).some((k) => k.level === "fail" && (k.blocks || []).includes("all"));
}
async function installNext() {
  if (!installQueue?.length) { installQueue = null; toast(lang === "ru" ? "Установка завершена" : "Installation finished"); await loadStatus(true); renderAll(); return; }
  const step = installQueue.shift();
  if (step === "gvhmr" && !$("install-terms").checked) { installQueue = null; toast(lang === "ru" ? "Отметьте согласие с условиями GVHMR" : "Accept the GVHMR terms", true); return; }
  setupRunning = true; renderStatus();
  try {
    const d = await api("/api/setup", { component: step, model: STATUS.settings.pose_model, ...(step === "gvhmr" ? { accept_model_terms: true } : {}) });
    watchJob(d.job, $("setup-job"), $("setup-bar"), $("setup-text"), async (j) => {
      setupRunning = false; await loadStatus(true); renderAll();
      if (j.code === 2) { installQueue = null; toast(lang === "ru" ? "Перезагрузите компьютер, затем снова нажмите «Установить всё рекомендуемое» — установка продолжится." : "Restart the computer, then press “Install everything recommended” again — it continues.", true); return; }
      if (j.code !== 0) { installQueue = null; return; }
      installNext();
    });
  } catch (e) { setupRunning = false; installQueue = null; renderStatus(); fail(e); }
}
$("pf-run").addEventListener("click", () => { runPreflight.manual = true; runPreflight(); });
let BENCH = null;
function renderBench() {
  const b = BENCH, box = $("bench-result");
  $("bench-apply").classList.toggle("hidden", !b?.recommend);
  if (!b?.measured) { box.textContent = ""; return; }
  const p = b.measured.resources || {}, gb = (mb) => mb ? (mb / 1024).toFixed(1) : "—", rec = b.recommend || {};
  box.replaceChildren(
    el("p", { text: (lang === "ru" ? `${b.time} · режим ${b.quality}: ${(b.measured.fps_processing || 0).toFixed(1)} кадр/с; пик видеопамяти ${gb(p.vram_mb)} из ${gb(p.vram_total_mb)} ГБ, ОЗУ ${gb(p.ram_mb)} из ${gb(p.ram_total_mb)} ГБ.`
      : `${b.time} · ${b.quality} mode: ${(b.measured.fps_processing || 0).toFixed(1)} frames/s; peak VRAM ${gb(p.vram_mb)} of ${gb(p.vram_total_mb)} GB, RAM ${gb(p.ram_mb)} of ${gb(p.ram_total_mb)} GB.`) }),
    rec.reason ? el("p", { class: "hint", text: (lang === "ru" ? "Рекомендуем: " : "Recommended: ") + L(rec.reason)
      + ` (${t("o_gemx_q_" + rec.quality) || rec.quality}; ${rec.chunk_seconds ? `${lang === "ru" ? "части по" : "parts of"} ${rec.chunk_seconds} ${lang === "ru" ? "с" : "s"}` : (lang === "ru" ? "без частей" : "no parts")}; ${lang === "ru" ? "людей до" : "people up to"} ${rec.max_people})` }) : null);
}
async function loadBench() { BENCH = await api("/api/benchmark").catch(() => null); renderBench(); }
$("bench-run").addEventListener("click", async () => {
  try {
    const d = await api("/api/benchmark", { quality: $("bench-quality").value });
    $("bench-run").disabled = true;
    watchJob(d.job, $("setup-job"), $("setup-bar"), $("setup-text"), async () => { $("bench-run").disabled = false; await loadBench(); });
  } catch (e) { fail(e); }
});
$("bench-apply").addEventListener("click", async () => {
  const r = BENCH?.recommend; if (!r) return;
  try { await api("/api/settings", { settings: { gemx_quality: r.quality, gemx_chunk_seconds: r.chunk_seconds || 0, max_people: r.max_people } });
    await loadStatus(true); toast(lang === "ru" ? "Настройки GEM-X для новых дублей обновлены" : "GEM-X defaults for new takes updated"); } catch (e) { fail(e); }
});
$("install-all").addEventListener("click", () => { if (setupRunning || installQueue !== null) return; installQueue = installPlan(); renderInstallPlan(); installNext(); });
$("open-demo").addEventListener("click", async () => {
  await loadTakes(); const demo = TAKES.find((x) => /sports2d|demo/i.test(x.id + " " + x.name));
  if (!demo) { toast(lang === "ru" ? "Демо-дубля нет: импортируйте любое видео на вкладке «Дубли»" : "No demo take: import any video on the Takes tab", true); return; }
  showView("takes"); openTake(demo.id);
});
$("support-report").addEventListener("click", async () => {
  $("support-report").disabled = true;
  try { const d = await api("/api/support-report", {}); toast(t("saved_to") + d.path); } catch (e) { fail(e); } finally { $("support-report").disabled = false; }
});
// «как исправить» для ошибки установки или обработки
const adviceCache = new Map();
async function showAdvice(box, text) {
  box.dataset.for = text;
  if (!text) { box.classList.add("hidden"); return; }
  let advice = adviceCache.get(text);
  if (!advice) { try { advice = (await api("/api/advise", { text })).advice; adviceCache.set(text, advice); } catch { advice = []; } }
  if (box.dataset.for !== text) return;  // пока ждали ответ, открыли другой дубль или другую ошибку
  box.classList.toggle("hidden", !advice.length);
  box.replaceChildren(...(advice.length ? [el("b", { text: lang === "ru" ? "Как исправить" : "How to fix" })] : []),
    ...advice.map((a) => el("div", { class: "advice-item" }, el("p", { text: L(a) }), fixButton(a.fix))));
}
$('status-open-settings').onclick = () => showView('settings');
// ---------------------------------------------------------------- статус и компоненты
function renderStatus() {
  const busy = setupRunning;
  renderInstallPlan();
  $('setup-recommended').disabled = busy;
  const c = STATUS.components, box = $("status-cards"); box.replaceChildren();
  const card = (ok, title, ...body) => box.append(el("div", { class: "scard " + (ok ? "ok" : "missing") }, el("h3", { text: title }), ...body));
  const link = (k, label) => el("button", { class: "small ghost", text: label, onclick: () => openUrl(c.links[k]) });


  const gx = c.gemx || {};
  card(gx.ready,"GEM-X · SOMA",el("p",{text:lang === "ru" ? "Тело, кисти и лицо: 77 суставов. Отдельная модель SOMA. Экспериментальная интеграция; статичная камера. Mac: ONNX / CoreML, Windows: WSL2 / NVIDIA." : "Body, hands and face: 77 SOMA joints. Experimental integration; static camera. Mac: ONNX / CoreML; Windows: WSL2 / NVIDIA."}),el("div",{class:"row"},el("button",{class:"small primary",text:gx.ready?t("s_installed"):t("s_install"),disabled:busy?"":null,onclick:()=>startSetup("gemx")}),el("button",{class:"small ghost",text:t("s_install_guide"),onclick:()=>openUrl("https://github.com/NVlabs/GEM-X")})));
  const gl = c.gvhmr_local;
  const ru = document.documentElement.lang.startsWith('ru');
  const terms = el('input', { type:'checkbox' });
  const install = el('button', {class:'small primary',text:ru?'Установить GVHMR на этом ПК':'Install GVHMR on this PC',disabled:''});
  terms.onchange = () => { install.disabled = busy || !terms.checked || !c.gpu.cuda || c.platform.system === "Darwin"; };
  install.onclick = () => startSetup('gvhmr',{accept_model_terms:terms.checked});
  card(gl.ready, t("s_gvhmr"),
    el('p',{text:gl.ready ? (ru?'Готово: загрузите видео и выберите «GVHMR · этот ПК».':'Ready: upload a video and select GVHMR · this PC.') :
      (ru?'Для своей NVIDIA: установите окружение и добавьте модель SMPL-X ниже. Пути настроятся автоматически.':'For your NVIDIA: install the environment and add SMPL-X below. Paths are configured automatically.')}),
    el('p',{text:gl.ready?'':t('s_gvhmr_missing')+gl.missing.map(m=>m==='environment'?(ru?'окружение':'environment'):t('missing_'+m)).join(', ')}),
    // на Mac локальный GVHMR не ставится (нужна NVIDIA) — не предлагаем согласие и установку
    c.platform.system === 'Darwin' ? null : el('label',{},terms, document.createTextNode(ru?' Я принимаю условия GVHMR и скачиваемых моделей (некоммерческое использование).':' I accept the GVHMR and downloaded model terms (non-commercial use).')),
    el('div',{class:'row'},c.platform.system === 'Darwin' || gl.ready ? null : install,link('gvhmr',t('s_install_guide'))),
    !gl.ready && c.platform.system !== 'Darwin' && !c.gpu.cuda ? el('p',{class:'hint',text:ru?'Видеокарта NVIDIA с CUDA не найдена — установка GVHMR недоступна; используйте Colab.':'No NVIDIA GPU with CUDA found — GVHMR install is unavailable; use Colab.'}) : null,
    c.platform.system === 'Windows' ? el('button',{class:'small ghost',text:ru?'Установить WSL / Ubuntu':'Install WSL / Ubuntu',disabled:busy?'':null,onclick:()=>startSetup('wsl')}) : null,
    el('p',{text:ru?'Windows: потребуется WSL2/Ubuntu; если их нет, программа покажет шаг установки. Mac: используйте Colab.':'Windows requires WSL2/Ubuntu; setup explains the prerequisite if missing. On Mac use Colab.'}),
    el('div',{class:'row'},el('button',{class:'small ghost',text:t('open_colab'),onclick:openColab}),
      el('a',{class:'button small ghost',href:withT('/api/colab-notebook'),text:t('download_notebook')})));
  card(!!c.smplx.path, t("s_smplx"), el("p", { text: t("s_smplx_desc") }), el("p", { text: c.smplx.path ? t("s_found") + c.smplx.path : t("s_not_found") }),
    el("div", { class: "row" }, el("label", { class: "button small" }, t("s_smplx_upload"),
      el("input", { type: "file", accept: ".npz,.zip", hidden: "", onchange: async (e) => {
        try {
          const u = await upload(e.target.files[0]); await api("/api/smplx", { upload: u.id }); await loadStatus(true); renderAll();
          toast(ru ? "Модель SMPL-X добавлена" : "SMPL-X model added");
          // инструменты SMPL-X (~1 ГБ) — только с согласия
          if (!STATUS.settings.gvhmr_python && confirm(ru ? "Подготовить инструменты SMPL-X (около 1 ГБ загрузки)?" : "Prepare SMPL-X tools (about 1 GB download)?")) await startSetup('smplx');
        } catch (er) { fail(er); }
      } })), link("smplx", t("s_smplx_site")), c.smplx.path && !STATUS.settings.gvhmr_python ? el('button',{class:'small ghost',text:ru?'Подготовить обработку SMPL-X':'Prepare SMPL-X tools',onclick:()=>startSetup('smplx')}) : null));
  for (const [k, desc] of [["blender", "s_blender_desc"], ["ffmpeg", "s_ffmpeg_desc"]]) {
    const p = c[k].path;
    card(!!p, t("s_" + k), el("p", { text: t(desc) }), el("p", { text: p ? t("s_found") + p : t("s_not_found") }),
      p ? null : el("div", { class: "row" }, el('button', {class:'small primary',text:t('s_install'),disabled:busy?'':null,onclick:()=>startSetup(k)}), link(k, t("s_download"))));
  }
}
$("refresh").addEventListener("click", () => loadStatus(true).then(renderAll).catch(fail));

// ---------------------------------------------------------------- настройки
let settingsDirty = false;
function renderSettings() {
  const s = STATUS.settings;
  const c = STATUS.components;
  $("rig-path-field").classList.toggle("hidden", $("s-rig").value !== "custom" && !(s.maya_rig && s.maya_rig !== "builtin"));
  const needed = [!c.ffmpeg.path ? 'FFmpeg' : '', !c.blender.path ? 'Blender' : ''].filter(Boolean);
  $('setup-readiness').textContent = needed.length ? t('setup_missing') + needed.join(', ') : t('setup_ready');
  $('setup-recommended').classList.toggle('hidden', !needed.length);  // всё стоит — не зовём ставить снова
  $("settings-file").textContent = t("settings_file") + STATUS.settings_file;
  if (settingsDirty) return;  // несохранённые правки не затираем при переключении вкладок и языка
  $("s-gemx-dir").value = s.gemx_dir || ""; $("s-gemx-python").value = s.gemx_python || ""; $("s-gemx-wsl").value = s.gemx_wsl || "";
  $("s-updates").checked = s.check_updates !== false;
  $("s-lang").value = s.lang; $("s-library").value = s.library || ""; $("s-library").placeholder = STATUS.library;
  $("s-backend").value = s.backend === "mediapipe" ? "gvhmr-colab" : s.backend; $("s-smplx").value = s.smplx_model; $("s-blender").value = s.blender;
  $("s-gvhmr-runtime").value = s.gvhmr_wsl || STATUS.platform === "Windows" ? "wsl" : "native";
  $("s-wsl-distro").value = s.gvhmr_wsl || "";
  $("wsl-distro-field").classList.toggle("hidden", $("s-gvhmr-runtime").value !== "wsl");
  $("s-maya").value = s.maya; $("s-gvhmr-dir").value = s.gvhmr_dir; $("s-gvhmr-py").value = s.gvhmr_python;
  buildOptions($("settings-opt-grid"), s, "gvhmr-local", "settings");
  $("s-rig").value = s.maya_rig === "builtin" ? "builtin" : s.maya_rig ? "custom" : "";
  $("s-rig-path").value = s.maya_rig && s.maya_rig !== "builtin" ? s.maya_rig : "";
  $("rig-path-field").classList.toggle("hidden", $("s-rig").value !== "custom");
}
function markSettingsDirty(e) {
  if (e.target.closest?.("#profile-title, .workbench-panel")) return;  // профили рига сохраняются своей кнопкой
  settingsDirty = true; $("s-saved").textContent = t("unsaved"); $("s-saved").classList.add("changed");
}
$("view-settings").addEventListener("input", markSettingsDirty);
$("view-settings").addEventListener("change", markSettingsDirty);
$("s-rig").addEventListener("change", () => $("rig-path-field").classList.toggle("hidden", $("s-rig").value !== "custom"));
$("s-gvhmr-runtime").addEventListener("change", () => $("wsl-distro-field").classList.toggle("hidden", $("s-gvhmr-runtime").value !== "wsl"));
$("s-save").addEventListener("click", async () => {
  try {
    const o = readOptions($("settings-opt-grid"));
    const d = await api("/api/settings", { settings: { check_updates: $("s-updates").checked, lang: $("s-lang").value, library: $("s-library").value.trim(),
      backend: $("s-backend").value, smplx_model: $("s-smplx").value.trim(), blender: $("s-blender").value.trim(),
      gvhmr_wsl: $("s-gvhmr-runtime").value === "wsl" ? $("s-wsl-distro").value.trim() : "",
      gemx_dir: $("s-gemx-dir").value.trim(), gemx_python: $("s-gemx-python").value.trim(), gemx_wsl: $("s-gemx-wsl").value.trim(), maya: $("s-maya").value.trim(), maya_rig: $("s-rig").value === "custom" ? $("s-rig-path").value.trim() : $("s-rig").value, gvhmr_dir: $("s-gvhmr-dir").value.trim(), gvhmr_python: $("s-gvhmr-py").value.trim(),
      mixamo_namespace: o.mixamo_namespace, body_surface: o.body_surface, capture_hands: o.capture_hands, capture_face: o.capture_face, hand_stability: o.hand_stability, smooth_body: o.smooth_body, smooth_hands: o.smooth_hands, smoothing: o.smoothing ?? STATUS.settings.smoothing, root: o.root, foot_lock: o.foot_lock, focal_mm: o.focal_mm, max_people: o.max_people,
      space: o.space || "global" } });
    settingsDirty = false; $("s-saved").classList.remove("changed");
    $("s-saved").textContent = t("saved"); setTimeout(() => { if (!settingsDirty) $("s-saved").textContent = ""; }, 4000);
    if (d.settings.lang) lang = d.settings.lang;
    checkUpdate();
    newBackend = d.settings.backend;
    await loadStatus(true); applyLang(); await loadTakes();
  } catch (e) { fail(e); }
});
$("lang").addEventListener("click", () => {
  lang = lang === "ru" ? "en" : "ru";
  api("/api/settings", { settings: { lang } }).catch(() => {});
  applyLang();
});
$("open-browser").addEventListener("click", () => api("/api/open-browser", {}).catch(fail));

// ---------------------------------------------------------------- камера
let stream = null, recorder = null, chunks = [], recBlob = null, recStart = 0, recTimer = null, landmarker = null, liveOn = false;
const liveDetails = new LiveDetails();
let liveGeneration = 0, liveVision = null, liveFiles = null;
const cam = $("cam");
async function listCameras() {
  const devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  const sel = $("cam-device"); const prev = sel.value || STATUS?.settings.camera_id;
  sel.replaceChildren(...devs.map((d, i) => el("option", { value: d.deviceId, text: d.label || `Camera ${i + 1}` })));
  if (prev && devs.some((d) => d.deviceId === prev)) sel.value = prev;
  return devs;
}
async function startCamera() {
  stopCamera();
  $("cam-err").textContent = "";
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("getUserMedia");
    const [w, h] = $("cam-res").value.split("x").map(Number);
    const id = $("cam-device").value;
    stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: {
      width: { ideal: w }, height: { ideal: h }, frameRate: { ideal: Number($("cam-fps").value) }, ...(id ? { deviceId: { exact: id } } : {}) } });
    cam.srcObject = stream; await cam.play();
    $("cam-off").classList.add("hidden"); $("rec").disabled = false;
    const devs = await listCameras();
    if (!devs.length) throw new Error(t("cam_none"));
    const cur = stream.getVideoTracks()[0]?.getSettings()?.deviceId;
    if (cur && devs.some((d) => d.deviceId === cur)) {
      $("cam-device").value = cur;
      api("/api/settings", { settings: { camera_id: cur } }).catch(() => {});
    }
    if ($("live-check").checked) startLive();
  } catch (e) {
    $("cam-off").classList.remove("hidden"); $("cam-err").textContent = t("cam_denied") + (e.message || e.name);
  }
}
function stopCamera() {
  liveOn = false; liveGeneration++; clearCamOverlay();
  if (recorder && recorder.state !== "inactive") recorder.stop();
  stream?.getTracks().forEach((tr) => tr.stop()); stream = null;
  if (cam) cam.srcObject = null;
  $("cam-off").classList.remove("hidden"); $("rec").disabled = true;
}
$("cam-start").addEventListener("click", startCamera);
["cam-device", "cam-res", "cam-fps"].forEach((id) => $(id).addEventListener("change", () => stream && startCamera()));
$("live-check").addEventListener("change", (e) => { if (e.target.checked && stream) startLive(); else { liveOn = false; clearCamOverlay(); $("live-hints").replaceChildren(); } });
$("cam-show-body").addEventListener("change", () => { if (!$("cam-show-body").checked) clearCamOverlay(); });
function clearCamOverlay() { const c = $("cam-overlay"); c.getContext("2d").clearRect(0, 0, c.width, c.height); }
function hint(level, key, extra = "") { return el("li", { class: level, text: t(key) + extra }); }
async function loadLiveDetails() {
  if (!liveVision || !liveFiles) return;
  const enabled = ['hand','face'].filter(k => $(k === 'hand' ? 'cam-show-hands' : 'cam-show-face').checked);
  $('live-detail-status').textContent = enabled.length ? (lang === 'ru' ? 'Загрузка трекеров кистей / лица…' : 'Loading hand / face trackers…') : '';
  const results = await Promise.allSettled(enabled.map(k => liveDetails.load(k, liveVision, liveFiles)));
  $('live-detail-status').textContent = results.filter(r => r.status === 'rejected').map(r => r.reason.message || String(r.reason)).join('; ') || (enabled.length ? (lang === 'ru' ? 'Слои готовы. Это предпросмотр; для экспорта включите кисти / лицо в параметрах обработки.' : 'Layers ready. Preview only; enable hands / face in processing options to export.') : '');
}
['cam-show-hands','cam-show-face'].forEach(id => $(id).addEventListener('change', () => {
  clearCamOverlay();
  if (!liveOn && stream) { $('live-check').checked = true; startLive(); }
  else if (liveOn) loadLiveDetails();
}));
async function startLive() {
  const generation = ++liveGeneration;
  liveOn = true;
  const hints = $("live-hints"); hints.replaceChildren(hint("", "h_loading"));
  try {
    if (!landmarker) {
      const vision = await import("/tasks-vision/vision_bundle.mjs");
      const files = await vision.FilesetResolver.forVisionTasks("/tasks-vision/wasm");
      liveVision = vision; liveFiles = files;
      const local = STATUS.components.mediapipe.models;
      const model = local.includes("lite") ? withT("/models/pose_landmarker_lite.task") : local.includes("full") ? withT("/models/pose_landmarker_full.task")
        : "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task";
      const make = (delegate) => vision.PoseLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: model, delegate },
        runningMode: "VIDEO", numPoses: STATUS.settings.max_people || 4 });
      landmarker = await make("GPU").catch(() => make("CPU"));
    }
    await landmarker.setOptions({ numPoses: STATUS.settings.max_people || 4 });
  } catch (e) { hints.replaceChildren(hint("bad", "h_failed", e.message || String(e))); liveOn = false; return; }
  if (generation !== liveGeneration || !liveOn || !stream) return;
  loadLiveDetails();
  const probe = document.createElement("canvas"); probe.width = 32; probe.height = 18;
  let lastT = -1, frameNo = 0, lastInference = -Infinity;
  const step = () => {
    if (!liveOn || !stream || generation !== liveGeneration) return;
    if (cam.readyState >= 2 && cam.currentTime !== lastT && performance.now()-lastInference >= 66) {
      lastT = cam.currentTime;
      const now = performance.now(); lastInference = now;
      let res;
      try { res = landmarker.detectForVideo(cam, now); }
      catch (e) { hints.replaceChildren(hint('bad','h_failed',e.message || String(e))); liveOn = false; clearCamOverlay(); return; }
      const detail = liveDetails.detect(cam, now, { hand: $('cam-show-hands').checked, face: $('cam-show-face').checked });
      if (Object.keys(liveDetails.errors).length) $('live-detail-status').textContent = Object.entries(liveDetails.errors).map(([k,v]) => `${k}: ${v}`).join('; ');
      const lm = res.landmarks?.[0];
      drawLive(res.landmarks || [], detail);
      if (frameNo++ % 10 === 0) liveHints(lm, probe);
    }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function drawLive(poses, details = {}) {
  const c = $("cam-overlay"), wrap = $("cam-wrap");
  const W = wrap.clientWidth, H = wrap.clientHeight, dpr = devicePixelRatio || 1;
  if (c.width !== W * dpr || c.height !== H * dpr) { c.width = W * dpr; c.height = H * dpr; }
  const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  if (!cam.videoWidth) return;
  const vw = cam.videoWidth, vh = cam.videoHeight, s = Math.min(W / vw, H / vh), ox = (W - vw * s) / 2, oy = (H - vh * s) / 2;
  const P = (p) => [ox + p.x * vw * s, oy + p.y * vh * s];
  g.lineWidth = 3; g.lineCap = "round";
  if ($("cam-show-body").checked) poses.forEach((lm, i) => {
    g.strokeStyle = ["#5cc3cf", "#f0a35e", "#e27870", "#9be25c"][i % 4];
    for (const [a, b] of MP_EDGES) { g.beginPath(); g.moveTo(...P(lm[a])); g.lineTo(...P(lm[b])); g.stroke(); }
  });
  drawDetails(g, P, details);
}
function liveHints(lm, probe) {
  const out = [];
  const pg = probe.getContext("2d", { willReadFrequently: true }); pg.drawImage(cam, 0, 0, 32, 18);
  const px = pg.getImageData(0, 0, 32, 18).data; let lum = 0;
  for (let i = 0; i < px.length; i += 4) lum += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
  lum /= px.length / 4;
  if (!lm) out.push(hint("bad", "h_none"));
  else {
    const key = [0, 15, 16, 27, 28, 31, 32];
    if (key.some((i) => lm[i].x < 0.01 || lm[i].x > 0.99 || lm[i].y < 0.01 || lm[i].y > 0.99 || (lm[i].visibility ?? 1) < 0.3)) out.push(hint("warn", "h_edges"));
    const ys = lm.map((p) => p.y), h = Math.max(...ys) - Math.min(...ys);
    if (h < 0.4) out.push(hint("warn", "h_far")); else if (h > 0.97) out.push(hint("warn", "h_near"));
    const legs = [25, 26, 27, 28].reduce((a, i) => a + (lm[i].visibility ?? 1), 0) / 4;
    if (legs < 0.5) out.push(hint("warn", "h_legs"));
  }
  if (lum < 55) out.push(hint("warn", "h_dark"));
  if (!out.length) out.push(hint("good", "h_ok"));
  $("live-hints").replaceChildren(...out);
}
$("rec").addEventListener("click", async () => {
  const cd = Number($("cam-cd").value);
  $("rec").disabled = true;
  for (let i = cd; i > 0; i--) { $("countdown").textContent = i; $("countdown").classList.remove("hidden"); await new Promise((r) => setTimeout(r, 1000)); }
  $("countdown").classList.add("hidden");
  const mime = ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm"].find((m) => window.MediaRecorder?.isTypeSupported?.(m));
  chunks = [];
  recorder = new MediaRecorder(stream, mime ? { mimeType: mime, videoBitsPerSecond: 8e6 } : {});
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = () => {
    clearInterval(recTimer); $("rec-dot").classList.add("hidden");
    recBlob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
    $("rec-preview").src = URL.createObjectURL(recBlob); $("rec-preview").classList.remove("hidden");
    fillRecBackends(); $("rec-done").classList.remove("hidden"); $("rec-stop").classList.add("hidden"); $("rec").classList.add("hidden");
    $("rec-name").value = "rec_" + new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  };
  recorder.start(500); recStart = Date.now();
  $("rec-dot").classList.remove("hidden"); $("rec-stop").classList.remove("hidden");
  recTimer = setInterval(() => { const s = Math.floor((Date.now() - recStart) / 1000); $("rec-time").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }, 250);
});
$("rec-stop").addEventListener("click", () => recorder?.state !== "inactive" && recorder.stop());
$("rec-again").addEventListener("click", resetRec);
function fillRecBackends() {
  const names = { "gemx-local": "GEM-X · SOMA", "gvhmr-local": `GVHMR · ${t("this_pc")}`, "gvhmr-colab": "GVHMR · Colab" };
  const ready = Object.keys(names).filter(backendReady);
  const preferred = [STATUS.settings.backend, "gemx-local", "gvhmr-local", "gvhmr-colab"].find((b) => ready.includes(b));
  $("rec-backend").replaceChildren(...Object.entries(names).map(([v, n]) => el("option", { value: v, text: backendReady(v) ? n : `${n} — ${t("not_installed")}` })));
  $("rec-backend").value = preferred || "gvhmr-colab";
}
function resetRec() {
  recBlob = null; $("rec-preview").classList.add("hidden"); $("rec-preview").removeAttribute("src");
  $("rec-done").classList.add("hidden"); $("rec").classList.remove("hidden"); $("rec").disabled = !stream;
}
$("rec-use").addEventListener("click", async () => {
  if (!recBlob) return;
  try {
    $("rec-use").disabled = true;
    const ext = recBlob.type.includes("mp4") ? "mp4" : "webm";
    const name = $("rec-name").value.trim() || "rec";
    const u = await upload(new File([recBlob], `${name}.${ext}`, { type: recBlob.type }));
    const backend = $("rec-backend").value;
    if (!backendReady(backend)) { showView("status"); throw Error(lang === "ru" ? "Эта модель не установлена — установите её в «Модели и инструменты»" : "This model is not installed — install it in Models & tools"); }
    const d = await api("/api/takes", { files: [u.id], name, backend, source: "camera", fps_hint: Number($("cam-fps").value) });
    resetRec(); showView("takes"); await loadTakes(); openTake(d.id, d.job);
  } catch (e) { fail(e); } finally { $("rec-use").disabled = false; }
});

workbench.init(()=>({lang,status:STATUS,take:TAKE,takes:TAKES,person:personId,api,withT,upload,fail,resizeViewer:()=>viewer3d?.resize(),seek:seekFrame,frame:currentFrame,fps,redraw:drawStrip,loadTakes,openTake,showView,refreshStatus:()=>loadStatus(true)}));
// ---------------------------------------------------------------- старт
// новая версия Studio — неназойливая кнопка в шапке
let UPDATE = null;
async function checkUpdate() {
  try { UPDATE = await api("/api/update"); } catch { UPDATE = null; }
  $("update-pill").classList.toggle("hidden", !UPDATE?.available);
  if (UPDATE?.available) $("update-pill").textContent = t("update_available").replace("{v}", UPDATE.version);
}
$("update-pill").addEventListener("click", () => UPDATE?.url && openUrl(UPDATE.url));
// загрузка компьютера в шапке: видеокарта, видеопамять, ОЗУ (во время обработки — и память WSL)
async function refreshLoad() {
  const busy = Object.keys(STATUS?.busy || {}).length > 0 || watching.size > 0;
  const r = await api(`/api/resources${busy ? "" : "?wsl=0"}`).catch(() => null);
  const pill = $("load-pill"); if (!r) return;
  const gb = (mb) => (mb / 1024).toFixed(1), g = (r.gpu || [])[0];
  const ram = r.wsl_ram_total_mb ? [r.wsl_ram_used_mb, r.wsl_ram_total_mb, "WSL "] : [r.ram_used_mb, r.ram_total_mb, ""];
  const parts = [g ? `GPU ${g.util ?? "—"}% · ${gb(g.vram_used_mb)}/${gb(g.vram_total_mb)}` : "", ram[1] ? `${lang === "ru" ? "ОЗУ" : "RAM"} ${ram[2]}${gb(ram[0])}/${gb(ram[1])}` : ""].filter(Boolean);
  pill.textContent = parts.join(" · ") + (parts.length ? (lang === "ru" ? " ГБ" : " GB") : "");
  pill.classList.toggle("hidden", !parts.length);
  pill.classList.toggle("hot", Boolean((g && g.vram_used_mb / g.vram_total_mb > 0.9) || (ram[1] && ram[0] / ram[1] > 0.9)));
}
$("load-pill").addEventListener("click", () => { showView("status"); setTimeout(() => $("bench-run").scrollIntoView({ block: "center", behavior: "smooth" }), 300); });
setInterval(() => { if (document.visibilityState === "visible") refreshLoad(); }, 5000);
(async () => {
  try {
    await loadStatus();
    applyLang();
    await loadTakes();
    await workbench.refreshProfiles();await workbench.queueRefresh();
    if (TAKES.length) openTake(TAKES[0].id); else showNew();
    checkUpdate(); refreshCharacters().catch(() => {});
    refreshLoad();
    // первый запуск без установленных моделей — сразу мастер установки
    let seen = "1"; try { seen = localStorage.getItem("mocapgate-setup-seen"); localStorage.setItem("mocapgate-setup-seen", "1"); } catch {}
    if (!seen && !STATUS.components.gemx?.ready && !STATUS.components.gvhmr_local.ready) showView("status");
    // идущие задачи (например, после перезагрузки страницы)
    for (const [take, job] of Object.entries(STATUS.busy || {})) if (take === CURRENT) watchJob(job, $("job"), $("job-bar"), $("job-text"), () => openTake(take));
  } catch (e) { fail(e); }
})();
