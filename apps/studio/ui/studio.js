// MoCapGate Studio — интерфейс. Чистый JS-модуль без сборки; three.js и MediaPipe Tasks грузятся лениво.
// Сервер: apps/studio/server.py (JSON-API на 127.0.0.1 с токеном сессии).

// ---------------------------------------------------------------- i18n
const STRINGS = {
  en: {
    skeleton_structure: "Skeleton structure", skeleton_tip_hint: "Terminal joints are fixed endpoints, not independently tracked.", o_mixamo_namespace: "Mixamo prefix mixamorig: (BVH / FBX)",
    studio: "Studio", person: "Person", o_people: "Maximum people (1–8)", tab_takes: "Takes", tab_camera: "Camera", tab_status: "Status & AI", tab_settings: "Settings",
    open_browser: "Open in browser", open_browser_hint: "The same app in your web browser (handy for the camera)",
    new_take: "+ New take", no_takes: "No takes yet. Drop a video here or record one with the camera.",
    reveal_library: "Show library folder", new_title: "New take",
    new_sub: "A video of a person → animation of a skeleton (BVH / FBX) for Blender, Maya and engines.",
    drop_title: "Drop a video here", drop_hint: "mp4, mov, webm — or a result from Colab (.zip / .mocapgate.json)",
    take_name: "Name", backend: "How to recognize the motion",
    be_mediapipe: "On this computer, no GPU. Body, optional hands and face. Quick to try.",
    be_colab: "Best quality: whole body in the world, on Google's free GPU. A few minutes.",
    be_local: "Same quality on your NVIDIA GPU — connect GVHMR in Status.", this_pc: "this PC",
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
    layer_detected: "Points found on the video", layer_skeleton: "Our skeleton projected back",
    three_hint: "Drag to turn, wheel to zoom. The grid is the floor, 1 m cells.",
    check_title: "How well the video was caught", tune_title: "Tune and process again", reprocess: "Process again",
    export_title: "Export", dl_bvh: "Download BVH", make_fbx: "Make FBX (Maya, Unity, Unreal)", dl_fbx: "Download FBX",
    open_blender: "Open in Blender", open_maya: "Open FBX in Maya", reveal: "Show in folder",
    export_hint: "Blender: File → Import → Motion Capture (.bvh), Scale 0.01. Maya: import the FBX, then HumanIK to retarget.",
    cam_off: "The camera is off.", cam_start: "Turn on the camera", cam_device: "Camera", cam_res: "Resolution",
    cam_countdown: "Countdown, s", live_check: "Live check: skeleton and hints", rec_start: "● Record", rec_stop: "■ Stop",
    rec_use: "Make a take from it", rec_again: "Record again",
    rec_backend_hint: "The take uses the recognition chosen in Settings; you can change it on the take.",
    tips_title: "How to film for good mocap",
    tip_1: "The whole body in frame, head to feet, with a little room around.",
    tip_2: "Camera at waist height, still (a tripod or a shelf).",
    tip_3: "Even light, no strong backlight; clothes that contrast with the background.",
    tip_4: "Start and end in a T-pose or standing still for a second.",
    tip_5: "Keep people separated and visible; avoid clothes that hide knees and elbows.",
    status_title: "Status & AI", status_sub: "What is found on this computer, what is missing and how to add it.",
    refresh: "Check again", settings_title: "Settings", set_lang: "Language", lang_auto: "As the system",
    set_library: "Takes folder", set_backend: "Recognition by default",
    set_smplx: "SMPL-X model (exact bone lengths for GVHMR)", set_blender: "Blender (if not found by itself)",
    set_maya: "Maya (optional)", set_gvhmr_dir: "GVHMR folder (NVIDIA GPU)", set_gvhmr_py: "Python of the GVHMR environment",
    save: "Save", saved: "Saved", settings_file: "Settings file: ",
    // options
    o_pose_model: "MediaPipe model", o_model_lite: "lite — fast", o_model_full: "full", o_model_heavy: "heavy — most accurate",
    o_smoothing: "Smoothing", o_root: "Root motion", o_root_image: "Move as in the video", o_root_inplace: "In place",
    o_surface: "Full SMPL-X avatar (local model required)", o_view_mode: "3D view", o_view_surface: "Body", o_view_bones: "Bones", o_view_both: "Body + bones", o_hands: "Hand fingers (BVH / FBX)", o_face: "Full face and expressions", o_detail_hint: "SMPL-X displays a neutral avatar with approximate facial expression fitting. Face data also exports as JSON. Feet: heel and toe only; individual toes are not detected.", o_details: "Hands / face data (JSON)", o_foot_lock: "Pin the feet to the floor", o_focal: "Camera focal length, mm (35 mm eq.)",
    o_focal_hint: "0 — find automatically. Phone main camera ≈ 26, ultra-wide ≈ 13, 2× ≈ 48",
    o_space: "GVHMR space", o_space_global: "World (with the path)", o_space_incam: "Relative to the camera",
    o_fps: "Frame rate (0 — from the file)", o_static: "The camera stands still (GVHMR)", o_gvhmr_f: "Focal for GVHMR, mm (0 — auto)",
    // statuses
    st_new: "new", st_processing: "processing", st_done: "done", st_error: "error", st_waiting: "waiting for Colab",
    frames: "frames", focal: "focal", uploading: "Uploading", uploaded: "uploaded",
    pick_files: "Pick a video or a result first", need_mediapipe: "Install MediaPipe in Status & AI first",
    need_local: "Connect GVHMR in Status & AI first (NVIDIA GPU)", colab_video_hint: "The video is kept in the take; send the same video to Colab.",
    started: "Processing started", saved_to: "Saved: ", deleted: "The take is moved to the library's .trash folder",
    confirm_delete: "Delete this take? It goes to the .trash folder inside the library.",
    fbx_done: "FBX is ready", processing_done: "Done",
    verdict_good: "A good take — ready to use.", verdict_warn: "Usable, but look at the notes below.",
    verdict_bad: "A weak take — better film again following the advice below.",
    r_found: "Person found in frames", r_found_adv: "Sometimes the person is lost — check the light and that nothing covers them.",
    r_gap: "Longest gap", r_gap_adv: "Gaps are filled with the neighbouring frames — motion freezes there.",
    r_out_of_frame: "Out of frame", r_out_of_frame_adv: "Keep the whole body in frame — step back or move the camera away.",
    r_size: "Size in frame", r_size_adv: "The person is small — come closer or film in a higher resolution.",
    r_vis_arms: "Arms visible", r_vis_arms_adv: "Arms are often hidden or blurred — film from the front, brighter light, contrasting sleeves.",
    r_vis_legs: "Legs visible", r_vis_legs_adv: "Legs are often hidden — the whole body in frame, contrasting trousers.",
    r_vis_head: "Head visible", r_vis_head_adv: "The face is often turned away or out of frame.",
    r_jitter: "Jitter", r_jitter_adv: "Raise the smoothing, or film with more light (less motion blur).",
    r_foot_skate: "Foot sliding", r_foot_skate_adv: "Turn on pinning the feet; one camera always leaves a little sliding — GVHMR is cleaner.",
    r_upper_body: "Upper body only", r_upper_body_adv: "The legs are not in frame, so they are kept straight and the feet are not pinned. For full-body mocap, film head to feet.",
    r_reprojection: "Skeleton matches the video", r_reprojection_adv: "The skeleton drifts from the video — check the focal length or try GVHMR.",
    bones_model: "bones from the SMPL-X model", bones_average: "average bone lengths",
    // live hints
    h_loading: "Loading the live check…", h_none: "No person in frame", h_edges: "Keep the whole body in frame (head, hands, feet)",
    h_far: "Too far — come closer", h_near: "Too close — step back", h_dark: "Too dark — add light",
    h_legs: "Legs are poorly visible", h_ok: "Everything is visible — ready to record", h_failed: "Live check unavailable: ",
    cam_denied: "No access to the camera: ", cam_none: "No camera found",
    // status cards
    s_python: "Python", s_gpu: "Graphics / compute", s_mediapipe: "MediaPipe — pose on this computer",
    s_mediapipe_desc: "Recognizes 33 body points in each frame on the CPU. Apache-2.0, ~1 GB, installed in its own folder.",
    s_install: "Install", s_installed: "Installed", s_models: "Models: ", s_get_model: "Download model",
    s_gvhmr: "GVHMR — best quality", s_gvhmr_colab: "In Google Colab (free GPU): no install on this computer.",
    s_gvhmr_local: "On this computer: needs an NVIDIA GPU and GVHMR installed by its guide; then set its folder in Settings.",
    s_gvhmr_ready: "GVHMR on this computer is ready", s_gvhmr_missing: "Missing for local GVHMR: ",
    s_smplx: "SMPL-X body model", s_smplx_desc: "Exact bone lengths for GVHMR takes (needs numpy). Free sign-up, non-commercial licence.",
    s_smplx_upload: "Upload SMPLX_NEUTRAL.npz", s_smplx_site: "Get it (smpl-x.is.tue.mpg.de)",
    s_blender: "Blender", s_blender_desc: "Makes FBX and opens takes with the animation.", s_maya: "Maya",
    s_maya_desc: "Optional: opens the FBX straight away (needs the FBX plug-in, on by default).",
    s_ffmpeg: "ffmpeg", s_ffmpeg_desc: "Turns camera recordings into mp4 with a steady frame rate; needed for local GVHMR.",
    s_uv: "uv", s_uv_desc: "Installs MediaPipe with the right Python version.", s_found: "Found: ", s_not_found: "Not found",
    s_download: "Download", s_install_guide: "How to install", missing_folder: "folder", missing_checkpoints: "weights",
    missing_smplx: "SMPL-X", missing_python: "python", missing_cuda: "NVIDIA GPU (CUDA)",
  },
  ru: {
    skeleton_structure: "Структура скелета", skeleton_tip_hint: "Окончания цепочек — фиксированные точки, без отдельного распознавания.", o_mixamo_namespace: "Префикс Mixamo mixamorig: (BVH / FBX)",
    studio: "Studio", person: "Участник", o_people: "Максимум людей (1–8)", tab_takes: "Дубли", tab_camera: "Камера", tab_status: "Статус и ИИ", tab_settings: "Настройки",
    open_browser: "Открыть в браузере", open_browser_hint: "То же приложение в браузере (удобно для камеры)",
    new_take: "+ Новый дубль", no_takes: "Дублей пока нет. Перетащите видео сюда или запишите с камеры.",
    reveal_library: "Папка библиотеки", new_title: "Новый дубль",
    new_sub: "Видео с человеком → анимация скелета (BVH / FBX) для Blender, Maya и движков.",
    drop_title: "Перетащите видео сюда", drop_hint: "mp4, mov, webm — или результат из Colab (.zip / .mocapgate.json)",
    take_name: "Название", backend: "Чем распознавать движение",
    be_mediapipe: "На этом компьютере, без видеокарты. Тело, кисти и лицо по выбору. Быстро попробовать.",
    be_colab: "Лучшее качество: всё тело в мировых координатах, на бесплатном GPU Google. Несколько минут.",
    be_local: "То же качество на вашей видеокарте NVIDIA — подключите GVHMR в «Статусе».", this_pc: "этот ПК",
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
    layer_detected: "Точки, найденные на видео", layer_skeleton: "Наш скелет, спроецированный обратно",
    three_hint: "Тяните — поворот, колесо — масштаб. Сетка — пол, клетка 1 м.",
    check_title: "Насколько хорошо поймано видео", tune_title: "Настроить и обработать заново", reprocess: "Обработать заново",
    export_title: "Экспорт", dl_bvh: "Скачать BVH", make_fbx: "Сделать FBX (Maya, Unity, Unreal)", dl_fbx: "Скачать FBX",
    open_blender: "Открыть в Blender", open_maya: "Открыть FBX в Maya", reveal: "Показать в папке",
    export_hint: "Blender: File → Import → Motion Capture (.bvh), Scale 0.01. Maya: импорт FBX, затем HumanIK для ретаргета.",
    cam_off: "Камера выключена.", cam_start: "Включить камеру", cam_device: "Камера", cam_res: "Разрешение",
    cam_countdown: "Обратный отсчёт, с", live_check: "Живая проверка: скелет и подсказки", rec_start: "● Записать", rec_stop: "■ Стоп",
    rec_use: "Сделать дубль", rec_again: "Переснять",
    rec_backend_hint: "Дубль распознаётся способом из «Настроек»; на дубле его можно поменять.",
    tips_title: "Как снимать для хорошего мокапа",
    tip_1: "Всё тело в кадре, от головы до стоп, с небольшим запасом.",
    tip_2: "Камера на уровне пояса и неподвижна (штатив или полка).",
    tip_3: "Ровный свет, без сильной засветки сзади; одежда контрастирует с фоном.",
    tip_4: "Начинайте и заканчивайте в T-позе или стоя неподвижно секунду.",
    tip_5: "Люди должны быть видны раздельно; одежда не должна скрывать колени и локти.",
    status_title: "Статус и ИИ", status_sub: "Что найдено на компьютере, чего не хватает и как добавить.",
    refresh: "Проверить заново", settings_title: "Настройки", set_lang: "Язык", lang_auto: "Как в системе",
    set_library: "Папка дублей", set_backend: "Распознавание по умолчанию",
    set_smplx: "Модель SMPL-X (точные длины костей для GVHMR)", set_blender: "Blender (если не нашёлся сам)",
    set_maya: "Maya (необязательно)", set_gvhmr_dir: "Папка GVHMR (видеокарта NVIDIA)", set_gvhmr_py: "Python окружения GVHMR",
    save: "Сохранить", saved: "Сохранено", settings_file: "Файл настроек: ",
    o_pose_model: "Модель MediaPipe", o_model_lite: "lite — быстрая", o_model_full: "full", o_model_heavy: "heavy — точнее всех",
    o_smoothing: "Сглаживание", o_root: "Движение корня", o_root_image: "Перемещаться как на видео", o_root_inplace: "На месте",
    o_surface: "Полная модель SMPL-X (нужна локальная модель)", o_view_mode: "Вид 3D", o_view_surface: "Тело", o_view_bones: "Кости", o_view_both: "Тело + кости", o_hands: "Пальцы рук (BVH / FBX)", o_face: "Полное лицо и мимика", o_detail_hint: "SMPL-X показывает нейтральный аватар с приблизительной мимикой. Данные лица также доступны в JSON. Стопы: пятка и носок; отдельные пальцы ног не распознаются.", o_details: "Кисти / лицо (JSON)", o_foot_lock: "Фиксировать стопы на полу", o_focal: "Фокус камеры, мм (35-мм экв.)",
    o_focal_hint: "0 — подобрать автоматически. Основная камера телефона ≈ 26, широкая ≈ 13, 2× ≈ 48",
    o_space: "Пространство GVHMR", o_space_global: "Мир (с траекторией)", o_space_incam: "Относительно камеры",
    o_fps: "Частота кадров (0 — из файла)", o_static: "Камера неподвижна (GVHMR)", o_gvhmr_f: "Фокус для GVHMR, мм (0 — авто)",
    st_new: "новый", st_processing: "обработка", st_done: "готов", st_error: "ошибка", st_waiting: "ждёт Colab",
    frames: "кадров", focal: "фокус", uploading: "Загрузка", uploaded: "загружено",
    pick_files: "Сначала выберите видео или результат", need_mediapipe: "Сначала установите MediaPipe в «Статус и ИИ»",
    need_local: "Сначала подключите GVHMR в «Статус и ИИ» (видеокарта NVIDIA)", colab_video_hint: "Видео сохранено в дубле; это же видео загрузите в Colab.",
    started: "Обработка запущена", saved_to: "Сохранено: ", deleted: "Дубль перенесён в папку .trash библиотеки",
    confirm_delete: "Удалить дубль? Он переместится в папку .trash внутри библиотеки.",
    fbx_done: "FBX готов", processing_done: "Готово",
    verdict_good: "Хороший дубль — можно в работу.", verdict_warn: "Годится, но посмотрите замечания ниже.",
    verdict_bad: "Слабый дубль — лучше переснять по советам ниже.",
    r_found: "Человек найден в кадрах", r_found_adv: "Иногда человек теряется — проверьте свет и чтобы его ничего не закрывало.",
    r_gap: "Самый долгий пропуск", r_gap_adv: "Пропуски заполнены соседними кадрами — там движение «замирает».",
    r_out_of_frame: "Выход из кадра", r_out_of_frame_adv: "Держите всё тело в кадре — отойдите или отодвиньте камеру.",
    r_size: "Размер в кадре", r_size_adv: "Человек мелко — подойдите ближе или снимайте в большем разрешении.",
    r_vis_arms: "Видимость рук", r_vis_arms_adv: "Руки часто закрыты или смазаны — снимайте спереди, свет ярче, рукава контрастнее.",
    r_vis_legs: "Видимость ног", r_vis_legs_adv: "Ноги часто не видны — всё тело в кадре, контрастные брюки.",
    r_vis_head: "Видимость головы", r_vis_head_adv: "Лицо часто отвёрнуто или вне кадра.",
    r_jitter: "Дрожание", r_jitter_adv: "Увеличьте сглаживание или снимайте при большем свете (меньше смаза).",
    r_foot_skate: "Проскальзывание стоп", r_foot_skate_adv: "Включите фиксацию стоп; с одной камеры немного скольжения остаётся всегда — у GVHMR чище.",
    r_upper_body: "Только верх тела", r_upper_body_adv: "Ноги не в кадре — они выставлены прямо, стопы не фиксируются. Для мокапа всего тела снимайте от головы до стоп.",
    r_reprojection: "Совпадение скелета с видео", r_reprojection_adv: "Скелет расходится с видео — проверьте фокус камеры или попробуйте GVHMR.",
    bones_model: "кости по модели SMPL-X", bones_average: "усреднённые длины костей",
    h_loading: "Загружаю живую проверку…", h_none: "Человека нет в кадре", h_edges: "Всё тело должно быть в кадре (голова, кисти, стопы)",
    h_far: "Далеко — подойдите ближе", h_near: "Слишком близко — отойдите", h_dark: "Темно — добавьте света",
    h_legs: "Ноги плохо видны", h_ok: "Всё видно — можно записывать", h_failed: "Живая проверка недоступна: ",
    cam_denied: "Нет доступа к камере: ", cam_none: "Камера не найдена",
    s_python: "Python", s_gpu: "Графика / вычисления", s_mediapipe: "MediaPipe — поза на этом компьютере",
    s_mediapipe_desc: "Находит 33 точки тела в каждом кадре на процессоре. Apache-2.0, ~1 ГБ, ставится в свою папку.",
    s_install: "Установить", s_installed: "Установлено", s_models: "Модели: ", s_get_model: "Скачать модель",
    s_gvhmr: "GVHMR — лучшее качество", s_gvhmr_colab: "В Google Colab (бесплатный GPU): ничего не ставится на компьютер.",
    s_gvhmr_local: "На этом компьютере: нужна видеокарта NVIDIA и GVHMR по его инструкции; затем укажите папку в «Настройках».",
    s_gvhmr_ready: "GVHMR на этом компьютере готов", s_gvhmr_missing: "Для локального GVHMR не хватает: ",
    s_smplx: "Модель тела SMPL-X", s_smplx_desc: "Точные длины костей для дублей GVHMR (нужен numpy). Бесплатная регистрация, некоммерческая лицензия.",
    s_smplx_upload: "Загрузить SMPLX_NEUTRAL.npz", s_smplx_site: "Где взять (smpl-x.is.tue.mpg.de)",
    s_blender: "Blender", s_blender_desc: "Делает FBX и открывает дубли с анимацией.", s_maya: "Maya",
    s_maya_desc: "Необязательно: открывает FBX сразу (нужен плагин FBX, он включён по умолчанию).",
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
function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
  document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = t(n.dataset.i18nTitle); });
  $("lang").textContent = lang === "ru" ? "EN" : "RU";
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
const fail = (e) => toast(String(e.message || e), true);
const openUrl = (url) => api("/api/open-url", { url }).catch(() => window.open(url, "_blank", "noopener"));

// ---------------------------------------------------------------- состояние
let STATUS = null;
let TAKES = [];
let CURRENT = null;      // id открытого дубля
let TAKE = null;         // его данные
let newBackend = "mediapipe";
let picked = [];         // [{file, id?, progress}]

async function loadStatus(refresh = false) {
  STATUS = await api("/api/status" + (refresh ? "?refresh=1" : ""));
  if (!lang) lang = STATUS.settings.lang || ((navigator.language || "en").toLowerCase().startsWith("ru") ? "ru" : "en");
  newBackend = newBackend || STATUS.settings.backend;
}
function renderAll() {
  if (!STATUS) return;
  renderPills(); renderStatus(); renderSettings(); renderTakeList(); renderBackendCards();
  buildOptions($("new-opt-grid"), STATUS.settings, newBackend, "new");
  if (TAKE) renderTake();
}
function renderPills() {
  const c = STATUS.components, p = $("pills"); p.replaceChildren();
  const pill = (ok, text) => p.append(el("span", { class: "pill " + (ok ? "ok" : "bad"), text }));
  pill(c.mediapipe.installed, "MediaPipe");
  pill(c.gvhmr_local.ready, "GVHMR " + (c.gvhmr_local.ready ? t("this_pc") : "· Colab"));
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
  if (v === "status") loadStatus().then(renderAll).catch(fail);
}

// ---------------------------------------------------------------- настройки обработки (общая форма)
const OPTS = [
  { k: "mixamo_namespace", type: "check", label: "o_mixamo_namespace" },
  { k: "body_surface", type: "check", label: "o_surface" },
  { k: "capture_hands", type: "check", label: "o_hands" },
  { k: "capture_face", type: "check", label: "o_face" },
  { k: "max_people", type: "number", for: ["mediapipe", "gvhmr-local"], min: 1, max: 8, step: 1, label: "o_people" },
  { k: "pose_model", type: "select", for: ["mediapipe"], vals: ["lite", "full", "heavy"], label: "o_pose_model", vl: (v) => t("o_model_" + v) },
  { k: "smoothing", type: "range", min: 0, max: 1, step: 0.05, label: "o_smoothing" },
  { k: "root", type: "select", vals: ["image", "inplace"], label: "o_root", vl: (v) => t("o_root_" + v) },
  { k: "foot_lock", type: "check", label: "o_foot_lock" },
  { k: "focal_mm", type: "number", for: ["mediapipe"], min: 0, max: 400, step: 1, label: "o_focal", hint: "o_focal_hint" },
  { k: "space", type: "select", for: ["gvhmr-colab", "gvhmr-local", "gvhmr-file"], vals: ["global", "incam"], label: "o_space", vl: (v) => t("o_space_" + v) },
  { k: "static_camera", type: "check", for: ["gvhmr-local"], label: "o_static" },
  { k: "gvhmr_f_mm", type: "number", for: ["gvhmr-local"], min: 0, max: 400, step: 1, label: "o_gvhmr_f" },
  { k: "fps", type: "number", for: ["take"], min: 0, max: 240, step: 1, label: "o_fps" },
];
function buildOptions(grid, values, backend, mode) {
  grid.replaceChildren();
  grid.append(el("small", { style: "grid-column: 1 / -1", text: t("o_detail_hint") }));
  const SETTINGS_KEYS = ["pose_model", "smoothing", "root", "foot_lock", "focal_mm", "space", "max_people", "capture_hands", "capture_face", "body_surface", "mixamo_namespace"];  // значения по умолчанию
  for (const o of OPTS) {
    if (mode === "settings") { if (!SETTINGS_KEYS.includes(o.k)) continue; }
    else if (o.k === "fps") { if (mode !== "take") continue; }
    else if (o.for && !o.for.includes(backend)) continue;
    const v = values[o.k] ?? (o.type === "check" ? false : o.type === "number" ? 0 : "");
    let input;
    if (o.type === "select") {
      input = el("select", { "data-k": o.k });
      for (const val of o.vals) input.append(el("option", { value: val, text: o.vl ? o.vl(val) : val }));
      input.value = v;
    } else if (o.type === "range") {
      const out = el("span", { class: "mono", text: Number(v).toFixed(2) });
      input = el("input", { type: "range", min: o.min, max: o.max, step: o.step, value: v, "data-k": o.k,
        oninput: (e) => { out.textContent = Number(e.target.value).toFixed(2); } });
      grid.append(el("label", { class: "field" }, el("span", { text: t(o.label) + " " }, out), input));
      continue;
    } else if (o.type === "check") {
      input = el("input", { type: "checkbox", "data-k": o.k });
      input.checked = !!v;
      grid.append(el("label", { class: "check" }, input, el("span", { text: t(o.label) })));
      continue;
    } else {
      input = el("input", { type: "number", min: o.min, max: o.max, step: o.step, value: v, "data-k": o.k });
    }
    grid.append(el("label", { class: "field" }, el("span", { text: t(o.label) }), input, o.hint ? el("small", { text: t(o.hint) }) : null));
  }
}
function readOptions(grid) {
  const out = {};
  grid.querySelectorAll("[data-k]").forEach((n) => {
    const o = OPTS.find((x) => x.k === n.dataset.k);
    out[n.dataset.k] = o.type === "check" ? n.checked : (o.type === "number" || o.type === "range") ? Number(n.value) : n.value;
  });
  return out;
}

// ---------------------------------------------------------------- новый дубль
function renderBackendCards() {
  const c = STATUS.components;
  document.querySelectorAll("#backend-cards .card").forEach((b) => {
    b.classList.toggle("on", b.dataset.backend === newBackend);
    if (b.dataset.backend === "gvhmr-local") b.title = c.gvhmr_local.ready ? "" : t("need_local");
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
  else if (!onlyResults && newBackend === "mediapipe" && !c.mediapipe.installed) hint = t("need_mediapipe");
  else if (!onlyResults && newBackend === "gvhmr-local" && !c.gvhmr_local.ready) hint = t("need_local");
  else if (newBackend === "gvhmr-colab" && !onlyResults) hint = t("colab_video_hint");
  $("start-hint").textContent = hint;
  $("start").disabled = !ready || (!onlyResults && ((newBackend === "mediapipe" && !c.mediapipe.installed) ||
    (newBackend === "gvhmr-local" && !c.gvhmr_local.ready)));
}
function renderPicked() {
  const box = $("picked"); box.replaceChildren();
  for (const p of picked) {
    const bar = el("div", { class: "bar" }, el("i", { style: `width:${Math.round((p.progress || 0) * 100)}%` }));
    box.append(el("div", {}, el("span", { text: p.file.name }), bar,
      el("small", { text: p.error ? p.error : p.id ? t("uploaded") : `${(p.file.size / 2 ** 20).toFixed(1)} MB` })));
  }
  updateStart();
}
async function addFiles(files) {
  for (const file of files) {
    const p = { file, progress: 0 };
    picked.push(p);
    if (!$("take-name").value) $("take-name").value = file.name.replace(/(\.mocapgate)?\.[^.]+$/, "").replace(/_mocapgate$/, "");
    renderPicked();
    upload(file, (f) => { p.progress = f; renderPicked(); })
      .then((d) => { p.id = d.id; p.progress = 1; renderPicked(); })
      .catch((e) => { p.error = e.message; renderPicked(); });
  }
}
function wireDrop(zone, input, onFiles) {
  zone.addEventListener("click", (e) => { if (e.target !== input) input.click(); });
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") input.click(); });
  input.addEventListener("change", () => { onFiles([...input.files]); input.value = ""; });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); onFiles([...e.dataTransfer.files]); });
}
wireDrop($("drop"), $("file-input"), addFiles);
// бросить файл в любое место вкладки «Дубли» — тоже новый дубль
$("view-takes").addEventListener("dragover", (e) => e.preventDefault());
$("view-takes").addEventListener("drop", (e) => {
  if (e.defaultPrevented) return;
  e.preventDefault(); showNew(); addFiles([...e.dataTransfer.files]);
});
$("new-take").addEventListener("click", showNew);
function showNew() {
  CURRENT = null; TAKE = null; picked = []; renderPicked(); $("take-name").value = "";
  $("new-panel").classList.remove("hidden"); $("take-panel").classList.add("hidden"); renderTakeList();
}
$("start").addEventListener("click", async () => {
  try {
    $("start").disabled = true;
    const d = await api("/api/takes", { files: picked.map((p) => p.id), name: $("take-name").value.trim(), backend: newBackend,
      options: readOptions($("new-opt-grid")), source: "file" });
    picked = []; renderPicked();
    toast(d.job ? t("started") : t("st_waiting"));
    await loadTakes(); openTake(d.id, d.job);
  } catch (e) { fail(e); updateStart(); }
});
function openColab() {
  openUrl(STATUS.colab_url);
  toast(t("colab_private_hint"));
}
$("open-colab").addEventListener("click", openColab);
$("open-colab-2").addEventListener("click", openColab);
$("dl-notebook").href = withT("/api/colab-notebook");
document.addEventListener("click", (e) => {  // ноутбук в окне приложения — тоже через «Загрузки»
  const a = e.target.closest?.('a[href*="/api/colab-notebook"]');
  if (!a || !STATUS?.desktop) return;
  e.preventDefault();
  api("/api/save-notebook", {}).then((d) => toast(t("saved_to") + d.path)).catch(fail);
});

// ---------------------------------------------------------------- список дублей
async function loadTakes() { TAKES = await api("/api/takes"); renderTakeList(); }
function renderTakeList() {
  const list = $("take-list"); list.replaceChildren();
  $("no-takes").classList.toggle("hidden", TAKES.length > 0);
  for (const tk of TAKES) {
    const st = tk.status === "waiting-result" ? "waiting" : tk.status;
    const badge = tk.status === "done" ? el("span", { class: "badge " + (tk.verdict || ""), text: String(tk.score ?? "") })
      : el("span", { class: "badge", text: t("st_" + st) });
    list.append(el("button", { class: "take-item" + (tk.id === CURRENT ? " on" : ""), onclick: () => openTake(tk.id) },
      el("b", { text: tk.name }), badge,
      el("small", { text: `${tk.created?.slice(5, 16) || ""} · ${tk.backend}${tk.frames ? ` · ${tk.frames} ${t("frames")}` : ""}` })));
  }
}
$("reveal-library").addEventListener("click", () => api("/api/reveal-library", {}).catch(fail));

// ---------------------------------------------------------------- дубль
let overlayData = null;
let overlayPeople = [];
const PERSON_COLORS = ["#f0a35e", "#5cc3cf", "#b493ef", "#e27870", "#9cce72", "#f0ce67", "#89a9ef", "#e992ca"];
const personColor = (id) => PERSON_COLORS[(id-1) % PERSON_COLORS.length];
const allPeopleText = () => lang === "ru" ? "Все участники" : "All participants";
function selectPerson() {
  TAKE = personId === 0 ? { ...sceneTake, bvh: null, fbx: null, report: null } :
    { ...sceneTake, fbx: null, ...sceneTake.people.find((p) => p.id === personId), id: sceneTake.id };
}
let viewer3d = null;
let personId = null, sceneTake = null, mediaRequest = 0;
$("person-select").addEventListener("change", () => {
  personId = Number($("person-select").value);
  selectPerson();
  renderTake(true);
});
async function openTake(id, jobId) {
  if (CURRENT !== id) personId = null;
  CURRENT = id;
  $("new-panel").classList.add("hidden"); $("take-panel").classList.remove("hidden");
  renderTakeList();
  TAKE = await api("/api/takes/" + id);
  sceneTake = TAKE;
  const participants = TAKE.people || [];
  if (participants.length) {
    if (personId !== 0 && !participants.some((p) => p.id === personId)) personId = participants.length > 1 ? 0 : participants[0].id;
    selectPerson();
  }
  overlayData = null;
  renderTake(true);
  const job = jobId || TAKE.job;
  if (job) watchJob(job, $("job"), $("job-bar"), $("job-text"), () => openTake(id));
}
function renderTake(fresh = false) {
  const tk = TAKE;
  $("person-picker").classList.toggle("hidden", (tk.people?.length || 0) < 2);
  $("person-select").replaceChildren(...((tk.people?.length || 0) > 1 ? [el("option", { value: 0, text: allPeopleText() })] : []),
    ...(tk.people || []).map((p) => el("option", { value: p.id, text: `${t("person")} ID ${p.id}` })));
  $("person-select").value = personId;
  $("export-person-hint").classList.toggle("hidden", personId !== 0);
  $("export-person-hint").textContent = lang === "ru" ? "Для скачивания или открытия анимации выберите ID участника сверху." : "Select a participant ID above to download or open an animation.";
  $("t-name").value = tk.name;
  const st = tk.status === "waiting-result" ? "waiting" : tk.status;
  $("t-badge").textContent = t("st_" + st); $("t-badge").className = "badge " + (tk.status === "done" ? tk.verdict : "");
  $("t-meta").textContent = [tk.backend, tk.fps ? `${tk.fps} fps` : "", tk.frames ? `${tk.frames} ${t("frames")}` : "",
    tk.focal_used ? `${t("focal")} ${tk.focal_used} mm` : "", tk.report ? t("bones_" + tk.report.bones) : ""].filter(Boolean).join(" · ");
  $("t-waiting").classList.toggle("hidden", tk.status !== "waiting-result");
  $("t-error").classList.toggle("hidden", !tk.error); $("t-error").textContent = tk.error || "";
  const done = tk.status === "done";
  $("t-viewer").classList.toggle("hidden", !done && !tk.video);
  document.querySelector(".below").classList.toggle("hidden", !done);
  if (done) {
    if (personId === 0) {
      $("score").textContent = `${tk.people.length}`; $("score").className = "score";
      $("verdict").textContent = allPeopleText();
      $("items").replaceChildren(...tk.people.map((p) => el("li", { class: p.report?.verdict || "" },
        el("b", { text: `${t("person")} ID ${p.id}` }), el("span", { class: "val", text: `${p.report?.score ?? "—"}/100` }))));
    } else renderReport(tk.report);
  }
  buildOptions($("take-opt-grid"), { ...STATUS.settings, ...(tk.options || {}) }, tk.backend, "take");  // старые дубли — недостающее из настроек
  $("dl-bvh").href = tk.bvh ? withT(`/files/${tk.id}/${encodeURIComponent(tk.bvh)}?download=1`) : "#";
  $("dl-fbx").classList.toggle("hidden", !tk.fbx);
  if (tk.fbx) $("dl-fbx").href = withT(`/files/${tk.id}/${encodeURIComponent(tk.fbx)}?download=1`);
  $("dl-bvh").classList.toggle("hidden", !tk.bvh);
  $("dl-capture").classList.toggle("hidden", !tk.capture_file || personId === 0);
  if (tk.capture_file) $("dl-capture").href = withT(`/files/${tk.id}/${encodeURIComponent(tk.capture_file)}?download=1`);
  const capturePeople = personId === 0 ? tk.people : [tk];
  $("capture-summary").textContent = (capturePeople || []).filter(p => p.capture_counts).map(p => {
    const c = p.capture_counts;
    const id = personId === 0 ? p.id : personId;
    return lang === "ru" ? `ID ${id}: левая кисть ${c.left}/${tk.frames}, правая ${c.right}/${tk.frames}, лицо ${c.face}/${tk.frames}. Пропуски означают, что деталь не распознана. Мимика — в JSON; пальцы — в BVH/FBX.` :
      `ID ${id}: left hand ${c.left}/${tk.frames}, right ${c.right}/${tk.frames}, face ${c.face}/${tk.frames}. Missing frames were not detected. Expressions: JSON; fingers: BVH/FBX.`;
  }).join(" ");
  $("make-fbx").disabled = !STATUS.components.blender.path; $("open-blender").disabled = !STATUS.components.blender.path || personId === 0;
  $("open-blender").title = personId === 0 ? (lang === "ru" ? "Для экспорта выберите ID участника" : "Select a participant ID to export") : "";
  $("open-maya").classList.toggle("hidden", !STATUS.components.maya.path); $("open-maya").disabled = !tk.fbx;
  if (fresh) loadMedia(tk);
}
async function loadMedia(tk) {
  const request = ++mediaRequest;
  const video = $("video");
  const desiredVideo = tk.video ? withT(`/files/${tk.id}/${encodeURIComponent(tk.video)}`) : null;
  if (tk.video) {
    if (video.getAttribute("src") !== desiredVideo) { video.pause(); video.src = desiredVideo; }
    $("novideo").classList.add("hidden");
  } else { video.removeAttribute("src"); video.load(); $("novideo").classList.remove("hidden"); }
  const participants = personId === 0 ? tk.people : [tk];
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
    surface: await loadSurface(p),
    overlayData: p.has_overlay ? await fetch(withT(`/files/${tk.id}/${encodeURIComponent(p.overlay || "overlay.json")}`)).then((r) => r.json()).catch(() => null) : null,
    text: tk.status === "done" && p.bvh ? await fetch(withT(`/files/${tk.id}/${encodeURIComponent(p.bvh)}`)).then((r) => { if (!r.ok) throw Error(r.statusText); return r.text(); }) : null,
    color: personColor(p.id === tk.id ? personId || 1 : p.id),
  })));
  if (request !== mediaRequest) return;
  overlayPeople = media;
  overlayData = media.find((p) => p.overlayData)?.overlayData || null;
  drawStrip();
  if (media.some((p) => p.text)) {
    if (!viewer3d) viewer3d = await import("/ui/viewer3d.js").then((m) => m.createViewer($("three")));
    if (request !== mediaRequest) return;
    viewer3d.loadScene(media.filter((p) => p.text));
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
      tree.append(el("h4", { text: `${t("person")} ID ${participant.id}` }), buildTree(root));
    });
    $("skeleton-panel").classList.toggle("hidden", !rigs.length);
    $("surface-mode-wrap").classList.toggle("hidden", !media.some(p => p.surface));
    viewer3d.setMode($("surface-mode").value);
  } else { viewer3d?.clear(); $("skeleton-panel").classList.add("hidden"); }
  syncFrame();
}
$("surface-mode").addEventListener("change", () => viewer3d?.setMode($("surface-mode").value));
$("t-name").addEventListener("change", () => api(`/api/takes/${CURRENT}/rename`, { name: $("t-name").value }).then(loadTakes).catch(fail));
$("t-delete").addEventListener("click", async () => {
  if (!confirm(t("confirm_delete"))) return;
  try { await api(`/api/takes/${CURRENT}/delete`, {}); toast(t("deleted")); await loadTakes(); showNew(); } catch (e) { fail(e); }
});
$("reprocess").addEventListener("click", async () => {
  try { const d = await api(`/api/takes/${CURRENT}/process`, { options: readOptions($("take-opt-grid")) }); openTake(CURRENT, d.job); } catch (e) { fail(e); }
});
$("make-fbx").addEventListener("click", async () => {
  try { const d = await api(`/api/takes/${CURRENT}/fbx`, {}); watchJob(d.job, $("job"), $("job-bar"), $("job-text"), () => { toast(t("fbx_done")); openTake(CURRENT); }); } catch (e) { fail(e); }
});
// в окне приложения скачивание идёт через сервер: файл копируется в «Загрузки» и показывается в папке
for (const [id, kind] of [["dl-bvh", "bvh"], ["dl-fbx", "fbx"]]) {
  $(id).addEventListener("click", (e) => {
    if (personId === 0) { e.preventDefault(); return; }
    if (!STATUS?.desktop) return;
    e.preventDefault();
    api(`/api/takes/${CURRENT}/save`, { kind, person: personId }).then((d) => toast(t("saved_to") + d.path)).catch(fail);
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
  vis_head: (v) => `${(v * 100).toFixed(0)}%`, jitter: (v) => `${v.toFixed(1)} m/s²`, foot_skate: (v) => `${v.toFixed(0)} cm/s`,
  reprojection: (v) => `${(v * 100).toFixed(1)}%`, upper_body: () => "",
};
function renderReport(rep) {
  if (!rep) return;
  $("score").textContent = rep.score; $("score").className = "score " + rep.verdict;
  $("verdict").textContent = t("verdict_" + rep.verdict);
  const ul = $("items"); ul.replaceChildren();
  for (const it of rep.items) {
    ul.append(el("li", { class: it.level }, el("b", { text: t("r_" + it.id) }),
      el("span", { class: "val", text: (FMT[it.id] || String)(it.value) }),
      it.level !== "good" ? el("small", { text: t("r_" + it.id + "_adv") }) : null));
  }
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
    if (detail && $("show-detected").checked) {
      g.strokeStyle = participant.color; g.fillStyle = participant.color; g.lineWidth = 1;
      for (const hand of Object.values(detail.hands || {})) {
        const pts = hand.image;
        for (const start of [1,5,9,13,17]) {
          g.beginPath(); g.moveTo(...P(pts[0]));
          for (let j=start;j<start+4;j++) g.lineTo(...P(pts[j]));
          g.stroke();
        }
        for (const p of pts) { const [x,y]=P(p); g.fillRect(x-1,y-1,2,2); }
      }
      if (detail.face) for (const p of detail.face.image) {
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
  if (!q.length) return;
  const w = c.width / q.length;
  q.forEach((v, i) => {
    g.fillStyle = v == null ? "#444" : v >= 0.75 ? "#3f8f58" : v >= 0.5 ? "#a27c4f" : "#a8524b";
    g.fillRect(i * w, 0, Math.ceil(w), 14);
  });
  const f = currentFrame();
  g.fillStyle = "#fff"; g.fillRect(f * w, 0, Math.max(2, w), 14);
}
$("strip").addEventListener("click", (e) => {
  const r = e.target.getBoundingClientRect(); const f = Math.floor((e.clientX - r.left) / r.width * frameCount());
  seekFrame(f);
});
function seekFrame(f) {
  if (TAKE?.video) video.currentTime = (f + 0.5) / fps(); else selfFrame = f;
  syncFrame();
}
function syncFrame() {
  const f = currentFrame(), n = frameCount();
  drawOverlay(f); drawStrip();
  viewer3d?.setFrame(f);
  $("seek").value = n ? Math.round(f / Math.max(1, n - 1) * 1000) : 0;
  $("time").textContent = `${f + 1} / ${n}`;
}
$("seek").addEventListener("input", (e) => seekFrame(Math.round(e.target.value / 1000 * Math.max(0, frameCount() - 1))));
$("play").addEventListener("click", () => {
  if (TAKE?.video) { video.paused ? video.play() : video.pause(); }
  else { selfPlaying = !selfPlaying; lastTs = 0; }
  $("play").textContent = (TAKE?.video ? !video.paused : selfPlaying) ? "❚❚" : "▶";
});
video.addEventListener("pause", () => { $("play").textContent = "▶"; });
video.addEventListener("play", () => { $("play").textContent = "❚❚"; });
$("speed").addEventListener("change", (e) => { video.playbackRate = Number(e.target.value); });
["show-detected", "show-skeleton"].forEach((id) => $(id).addEventListener("change", syncFrame));
video.addEventListener("seeked", syncFrame);
video.addEventListener("loadedmetadata", syncFrame);
function loop(ts) {
  if (view === "takes" && TAKE) {
    if (!TAKE.video && selfPlaying && frameCount()) {
      if (lastTs) selfFrame = (selfFrame + (ts - lastTs) / 1000 * fps() * Number($("speed").value)) % frameCount();
      lastTs = ts; syncFrame();
    } else if (TAKE.video && !video.paused) syncFrame();
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
addEventListener("resize", () => { syncFrame(); viewer3d?.resize(); });

// ---------------------------------------------------------------- задачи
const watching = new Map();
function watchJob(id, box, bar, text, onDone) {
  if (watching.has(id)) return;
  watching.set(id, true);
  box.classList.remove("hidden"); bar.parentElement.classList.add("indeterminate"); bar.style.width = "0";
  let since = 0;
  const cancel = box.querySelector("button");
  if (cancel) cancel.onclick = () => api(`/api/jobs/${id}/cancel`, {}).catch(fail);
  const log = box.id === "setup-job" ? $("setup-log") : null;
  if (log) { log.textContent = ""; log.classList.remove("hidden"); }
  const tick = async () => {
    try {
      const j = await api(`/api/jobs/${id}?since=${since}`);
      since = j.next;
      for (const ln of j.lines) {
        if (ln.message) text.textContent = ln.message;
        if (typeof ln.progress === "number") { bar.parentElement.classList.remove("indeterminate"); bar.style.width = `${Math.round(ln.progress * 100)}%`; }
        if (log && ln.message) log.textContent += ln.message + "\n";
      }
      if (j.done) {
        watching.delete(id);
        box.classList.add("hidden");
        if (j.code !== 0 && !j.cancelled) toast(text.textContent || "error", true);
        await loadTakes().catch(() => {});
        onDone?.(j);
        return;
      }
    } catch (e) { watching.delete(id); box.classList.add("hidden"); fail(e); return; }
    setTimeout(tick, 500);
  };
  tick();
}

// ---------------------------------------------------------------- статус и компоненты
function renderStatus() {
  const c = STATUS.components, box = $("status-cards"); box.replaceChildren();
  const card = (ok, title, ...body) => box.append(el("div", { class: "scard " + (ok ? "ok" : "missing") }, el("h3", { text: title }), ...body));
  const link = (k, label) => el("button", { class: "small ghost", text: label, onclick: () => openUrl(c.links[k]) });
  card(c.python.ok, t("s_python"), el("p", { text: `${c.python.version} — ${c.python.path}` }));
  card(true, t("s_gpu"), el("p", { text: `${c.gpu.name} (${c.gpu.kind})` }));
  const mp = c.mediapipe;
  const modelSel = el("select", {}, ...Object.keys(STATUS.pose_models).map((m) => el("option", { value: m, text: t("o_model_" + m) })));
  modelSel.value = STATUS.settings.pose_model;
  card(mp.installed, t("s_mediapipe"), el("p", { text: t("s_mediapipe_desc") }),
    el("p", { text: mp.installed ? t("s_installed") + ` · ${t("s_models")}${mp.models.join(", ") || "—"}` : (mp.uv ? "" : "uv: " + t("s_not_found")) }),
    el("div", { class: "row" }, modelSel,
      el("button", { class: "small primary", text: mp.installed ? t("s_get_model") : t("s_install"), disabled: !mp.uv && !mp.installed ? "" : null,
        onclick: () => api("/api/setup", { component: mp.installed ? "mediapipe-model" : "mediapipe", model: modelSel.value })
          .then((d) => watchJob(d.job, $("setup-job"), $("setup-bar"), $("setup-text"), () => loadStatus(true).then(renderAll))).catch(fail) }),
      mp.uv ? null : link("uv", t("s_install_guide"))));
  const gl = c.gvhmr_local;
  card(true, t("s_gvhmr"), el("p", { text: t("s_gvhmr_colab") }),
    el("div", { class: "row" }, el("button", { class: "small primary", text: t("open_colab"), onclick: openColab }),
      el("a", { class: "button small ghost", href: withT("/api/colab-notebook"), text: t("download_notebook") })),
    el("p", { text: t("s_gvhmr_local") }),
    el("p", { text: gl.ready ? t("s_gvhmr_ready") : t("s_gvhmr_missing") + gl.missing.map((m) => t("missing_" + m)).join(", ") }),
    el("div", { class: "row" }, link("gvhmr", t("s_install_guide"))));
  card(!!c.smplx.path, t("s_smplx"), el("p", { text: t("s_smplx_desc") }), el("p", { text: c.smplx.path ? t("s_found") + c.smplx.path : t("s_not_found") }),
    el("div", { class: "row" }, el("label", { class: "button small" }, t("s_smplx_upload"),
      el("input", { type: "file", accept: ".npz", hidden: "", onchange: async (e) => {
        try { const u = await upload(e.target.files[0]); await api("/api/smplx", { upload: u.id }); await loadStatus(true); renderAll(); } catch (er) { fail(er); }
      } })), link("smplx", t("s_smplx_site"))));
  for (const [k, desc] of [["blender", "s_blender_desc"], ["maya", "s_maya_desc"], ["ffmpeg", "s_ffmpeg_desc"], ["uv", "s_uv_desc"]]) {
    const p = c[k].path;
    card(!!p, t("s_" + k), el("p", { text: t(desc) }), el("p", { text: p ? t("s_found") + p : t("s_not_found") }),
      p ? null : el("div", { class: "row" }, link(k, t("s_download"))));
  }
}
$("refresh").addEventListener("click", () => loadStatus(true).then(renderAll).catch(fail));

// ---------------------------------------------------------------- настройки
function renderSettings() {
  const s = STATUS.settings;
  $("settings-file").textContent = t("settings_file") + STATUS.settings_file;
  $("s-lang").value = s.lang; $("s-library").value = s.library || ""; $("s-library").placeholder = STATUS.library;
  $("s-backend").value = s.backend; $("s-smplx").value = s.smplx_model; $("s-blender").value = s.blender;
  $("s-maya").value = s.maya; $("s-gvhmr-dir").value = s.gvhmr_dir; $("s-gvhmr-py").value = s.gvhmr_python;
  buildOptions($("settings-opt-grid"), s, "mediapipe", "settings");
}
$("s-save").addEventListener("click", async () => {
  try {
    const o = readOptions($("settings-opt-grid"));
    const d = await api("/api/settings", { settings: { lang: $("s-lang").value, library: $("s-library").value.trim(),
      backend: $("s-backend").value, smplx_model: $("s-smplx").value.trim(), blender: $("s-blender").value.trim(),
      maya: $("s-maya").value.trim(), gvhmr_dir: $("s-gvhmr-dir").value.trim(), gvhmr_python: $("s-gvhmr-py").value.trim(),
      mixamo_namespace: o.mixamo_namespace, body_surface: o.body_surface, capture_hands: o.capture_hands, capture_face: o.capture_face, pose_model: o.pose_model, smoothing: o.smoothing, root: o.root, foot_lock: o.foot_lock, focal_mm: o.focal_mm, max_people: o.max_people,
      space: o.space || "global" } });
    $("s-saved").textContent = t("saved");
    if (d.settings.lang) lang = d.settings.lang;
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
  liveOn = false;
  if (recorder && recorder.state !== "inactive") recorder.stop();
  stream?.getTracks().forEach((tr) => tr.stop()); stream = null;
  if (cam) cam.srcObject = null;
  $("cam-off").classList.remove("hidden"); $("rec").disabled = true;
}
$("cam-start").addEventListener("click", startCamera);
["cam-device", "cam-res", "cam-fps"].forEach((id) => $(id).addEventListener("change", () => stream && startCamera()));
$("live-check").addEventListener("change", (e) => { if (e.target.checked && stream) startLive(); else { liveOn = false; clearCamOverlay(); $("live-hints").replaceChildren(); } });
function clearCamOverlay() { const c = $("cam-overlay"); c.getContext("2d").clearRect(0, 0, c.width, c.height); }
function hint(level, key, extra = "") { return el("li", { class: level, text: t(key) + extra }); }
async function startLive() {
  liveOn = true;
  const hints = $("live-hints"); hints.replaceChildren(hint("", "h_loading"));
  try {
    if (!landmarker) {
      const vision = await import("/tasks-vision/vision_bundle.mjs");
      const files = await vision.FilesetResolver.forVisionTasks("/tasks-vision/wasm");
      const local = STATUS.components.mediapipe.models;
      const model = local.includes("lite") ? withT("/models/pose_landmarker_lite.task") : local.includes("full") ? withT("/models/pose_landmarker_full.task")
        : "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task";
      const make = (delegate) => vision.PoseLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: model, delegate },
        runningMode: "VIDEO", numPoses: STATUS.settings.max_people || 4 });
      landmarker = await make("GPU").catch(() => make("CPU"));
    }
    await landmarker.setOptions({ numPoses: STATUS.settings.max_people || 4 });
  } catch (e) { hints.replaceChildren(hint("bad", "h_failed", e.message || String(e))); liveOn = false; return; }
  const probe = document.createElement("canvas"); probe.width = 32; probe.height = 18;
  let lastT = -1, frameNo = 0;
  const step = () => {
    if (!liveOn || !stream) return;
    if (cam.readyState >= 2 && cam.currentTime !== lastT) {
      lastT = cam.currentTime;
      const res = landmarker.detectForVideo(cam, performance.now());
      const lm = res.landmarks?.[0];
      drawLive(res.landmarks || []);
      if (frameNo++ % 10 === 0) liveHints(lm, probe);
    }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function drawLive(poses) {
  const c = $("cam-overlay"), wrap = $("cam-wrap");
  const W = wrap.clientWidth, H = wrap.clientHeight, dpr = devicePixelRatio || 1;
  if (c.width !== W * dpr || c.height !== H * dpr) { c.width = W * dpr; c.height = H * dpr; }
  const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  if (!poses.length || !cam.videoWidth) return;
  const vw = cam.videoWidth, vh = cam.videoHeight, s = Math.min(W / vw, H / vh), ox = (W - vw * s) / 2, oy = (H - vh * s) / 2;
  const P = (p) => [ox + p.x * vw * s, oy + p.y * vh * s];
  g.lineWidth = 3; g.lineCap = "round";
  poses.forEach((lm, i) => {
    g.strokeStyle = ["#5cc3cf", "#f0a35e", "#e27870", "#9be25c"][i % 4];
    for (const [a, b] of MP_EDGES) { g.beginPath(); g.moveTo(...P(lm[a])); g.lineTo(...P(lm[b])); g.stroke(); }
  });
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
    $("rec-done").classList.remove("hidden"); $("rec-stop").classList.add("hidden"); $("rec").classList.add("hidden");
    $("rec-name").value = "rec_" + new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  };
  recorder.start(500); recStart = Date.now();
  $("rec-dot").classList.remove("hidden"); $("rec-stop").classList.remove("hidden");
  recTimer = setInterval(() => { const s = Math.floor((Date.now() - recStart) / 1000); $("rec-time").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }, 250);
});
$("rec-stop").addEventListener("click", () => recorder?.state !== "inactive" && recorder.stop());
$("rec-again").addEventListener("click", resetRec);
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
    const backend = STATUS.settings.backend === "gvhmr-local" && !STATUS.components.gvhmr_local.ready ? "mediapipe" : STATUS.settings.backend;
    const d = await api("/api/takes", { files: [u.id], name, backend, source: "camera", fps_hint: Number($("cam-fps").value) });
    resetRec(); showView("takes"); await loadTakes(); openTake(d.id, d.job);
  } catch (e) { fail(e); } finally { $("rec-use").disabled = false; }
});

// ---------------------------------------------------------------- старт
(async () => {
  try {
    await loadStatus();
    applyLang();
    await loadTakes();
    if (TAKES.length) openTake(TAKES[0].id); else showNew();
    // идущие задачи (например, после перезагрузки страницы)
    for (const [take, job] of Object.entries(STATUS.busy || {})) if (take === CURRENT) watchJob(job, $("job"), $("job-bar"), $("job-text"), () => openTake(take));
  } catch (e) { fail(e); }
})();
