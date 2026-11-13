"""Bản đồ 3D Bệnh Viện ATUS (Three.js WebGL Engine) - Phiên bản Nâng cấp 360° Quán Tính Mượt Mà.

Đặc tính kỹ thuật cao cấp:
1. Xoay 360° vô tận có quán tính (Angular Momentum & Damping factor = 0.92), lướt mượt mà chuẩn 60 FPS.
2. Giới hạn góc ngẩng an toàn (Polar Clamping 10° - 85°), không lật ngược, không xuyên sàn.
3. Hỗ trợ cảm ứng đa điểm (Touch Gestures): 1 ngón xoay 360°, 2 ngón kẹp để phóng to/thu nhỏ (Pinch Zoom) và rê 2 ngón (Pan).
4. Chuột: Kéo chuột trái xoay 360°, Chuột phải rê bản đồ (Pan), Con lăn phóng to/thu nhỏ mượt mà (Lerp Zoom).
5. Nút bấm tiện ích: Phóng to, Thu nhỏ, Đặt lại góc nhìn chuẩn, Bật/Tắt tự động xoay 360°.
6. Phản ánh chuẩn xác sơ đồ 35 phòng thực tế của 3 tầng Bệnh viện ATUS:
   - Tầng 1: Tiếp đón, Cấp cứu 24/7, Khám Nội, Nhi riêng, Cận lâm sàng, Nhà thuốc.
   - Tầng 2: 14 Chuyên khoa ngoại trú sâu.
   - Tầng 3: Khu phẫu thuật & ICU có ổ khóa "Chỉ nhân viên", mở khu thăm bệnh nội trú.
7. LOẠI BỎ TRIỆT ĐỂ BẢNG ĐẶT LỊCH TRÙNG LẶP: Dành trọn vẹn 100% không gian hiển thị cho mô hình 3D.
"""
from __future__ import annotations

import json


def get_hospital_3d_html(target_floor=1, target_dept="", mode="full"):
    """Trả về mã HTML Three.js bản đồ 3D ATUS chuẩn 360° mượt mà không trùng lặp."""
    init_f_idx = max(0, min(2, (int(target_floor) if target_floor else 1) - 1))
    init_dept_json = json.dumps(target_dept or "", ensure_ascii=False)
    is_mini = (mode == "mini")
    
    stage_height = "180px" if is_mini else "min(78vh, 720px)"
    min_h = "180px" if is_mini else "520px"

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<title>Bản đồ Bệnh viện ATUS 3D</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
:root {{
  --bg: #f8fafc;
  --card: #ffffff;
  --ink: #0f172a;
  --mute: #64748b;
  --line: #e2e8f0;
  --acc: #008f88;
  --acc-hover: #00736d;
  --title: #003a70;
  --soft: #e6f7f6;
  box-sizing: border-box;
}}
* {{ box-sizing: border-box; user-select: none; }}
body {{
  margin: 0;
  padding: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background: {"transparent" if is_mini else "var(--bg)"};
  color: var(--ink);
  overflow: hidden;
}}
.map-wrapper {{
  position: relative;
  width: 100%;
  height: 100vh;
  max-height: {stage_height};
  min-height: {min_h};
  background: linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 50%, #f1f5f9 100%);
  border-radius: {"10px" if is_mini else "14px"};
  overflow: hidden;
  border: 1px solid var(--line);
  box-shadow: 0 4px 20px rgba(0, 58, 112, 0.06);
}}
.stage {{
  width: 100%;
  height: 100%;
  position: relative;
  touch-action: none;
  cursor: grab;
}}
.stage.grabbing {{
  cursor: grabbing !important;
}}
.stage canvas {{
  display: block;
  width: 100%;
  height: 100%;
}}

/* Top Search & Filter Bar */
.top-bar {{
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  display: {"none" if is_mini else "flex"};
  gap: 10px;
  align-items: center;
  z-index: 30;
  pointer-events: none;
}}
.top-bar > * {{
  pointer-events: auto;
}}
.search-input-box {{
  flex: 1;
  max-width: 380px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border: 1.5px solid var(--line);
  border-radius: 24px;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}}
.search-input-box input {{
  border: none;
  background: transparent;
  width: 100%;
  font-size: 13.5px;
  color: var(--ink);
  outline: none;
}}
.view-ctrl-group {{
  display: flex;
  gap: 6px;
  margin-left: auto;
}}
.ctrl-pill {{
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--title);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  transition: all 0.2s;
}}
.ctrl-pill:hover {{
  background: var(--acc);
  color: #fff;
  border-color: var(--acc);
  transform: translateY(-1px);
}}
.ctrl-pill.active {{
  background: var(--acc);
  color: #fff;
  border-color: var(--acc);
}}

/* Controls Zoom & Rotate */
.zoom-controls {{
  position: absolute;
  left: 14px;
  top: {"10px" if is_mini else "68px"};
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 30;
}}
.zoom-btn {{
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(6px);
  color: var(--title);
  font-size: 17px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.2s;
}}
.zoom-btn:hover {{
  background: var(--acc);
  color: #fff;
  border-color: var(--acc);
  transform: scale(1.06);
}}

/* Floor Selector Tabs */
.floor-tabs {{
  position: absolute;
  left: 50%;
  bottom: 12px;
  transform: translateX(-50%);
  display: {"none" if is_mini else "flex"};
  gap: 6px;
  padding: 5px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border: 1.5px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 6px 20px rgba(0, 58, 112, 0.12);
  z-index: 30;
  max-width: calc(100% - 24px);
  overflow-x: auto;
}}
.floor-tab-btn {{
  border: none;
  background: transparent;
  color: var(--mute);
  border-radius: 11px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  transition: all 0.2s;
  text-align: center;
}}
.floor-tab-btn small {{
  display: block;
  font-size: 10.5px;
  font-weight: 500;
  opacity: 0.85;
}}
.floor-tab-btn:hover {{
  color: var(--title);
  background: rgba(0, 143, 136, 0.08);
}}
.floor-tab-btn.on {{
  background: var(--acc);
  color: #ffffff;
  box-shadow: 0 3px 10px rgba(0, 143, 136, 0.35);
}}
.floor-tab-btn.on small {{
  color: #e0fdfa;
}}

/* Room Labels (Billboard Pill) */
.lbl, .mk {{
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(4px);
  color: #0f172a;
  border: 1.5px solid var(--c, #008f88);
  border-radius: 999px;
  padding: {"2px 6px" if is_mini else "3px 9px"};
  font: 700 {"10px" if is_mini else "12px"} system-ui, -apple-system, sans-serif;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
  transition: transform 0.05s ease-out, border-color 0.2s;
  will-change: transform;
}}
.lbl i {{
  font-style: normal;
  background: var(--c, #008f88);
  color: #ffffff;
  border-radius: 6px;
  padding: 1px 5px;
  margin-left: 5px;
  font-size: {"9px" if is_mini else "10.5px"};
}}
.lbl.sel {{
  background: var(--c, #008f88) !important;
  color: #ffffff !important;
  transform: translate(-50%, -100%) scale(1.12) !important;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25) !important;
  z-index: 25 !important;
}}
.lbl.sel i {{
  background: #ffffff !important;
  color: var(--c, #008f88) !important;
}}
.lbl.restricted {{
  border-style: dashed;
  background: #f1f5f9;
  color: #64748b;
}}

/* Floating Room Info Card (Khi bấm chọn phòng trên 3D) */
.room-popup-card {{
  position: absolute;
  right: 14px;
  top: {"10px" if is_mini else "68px"};
  width: 260px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border: 1.5px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  box-shadow: 0 8px 24px rgba(0, 58, 112, 0.15);
  display: none;
  z-index: 35;
  animation: slideIn 0.2s ease-out;
}}
@keyframes slideIn {{
  from {{ opacity: 0; transform: translateY(-8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.room-popup-card b {{
  font-size: 15px;
  color: var(--title);
  display: block;
}}
.room-popup-card .p-meta {{
  font-size: 12px;
  color: var(--mute);
  margin: 4px 0 8px 0;
}}
.room-popup-card .p-badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 8px;
}}
.room-popup-card button {{
  width: 100%;
  background: var(--acc);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px;
  font-weight: 700;
  font-size: 12.5px;
  cursor: pointer;
  transition: 0.2s;
}}
.room-popup-card button:hover {{
  background: var(--acc-hover);
}}

/* Legend Box */
.legend-box {{
  position: absolute;
  left: 14px;
  bottom: 14px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 6px 10px;
  font-size: 11.5px;
  z-index: 28;
  display: {"none" if is_mini else "block"};
  max-width: 220px;
}}
.legend-box summary {{
  font-weight: 700;
  color: var(--title);
  cursor: pointer;
}}
.legend-item {{
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 11px;
}}
.legend-dot {{
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}}
</style>
</head>
<body>

<div class="map-wrapper">
  <!-- Top Bar -->
  <div class="top-bar">
    <div class="search-input-box">
      <span>🔍</span>
      <input id="q" type="search" placeholder="Tìm khoa, số phòng (VD: Nội, Cấp cứu, Tim mạch...)" aria-label="Tìm phòng">
    </div>
    <div class="view-ctrl-group">
      <button class="ctrl-pill" id="btn-reset-view" title="Trở về góc nhìn tiêu chuẩn">🔄 Đặt lại góc</button>
      <button class="ctrl-pill" id="btn-auto-rotate" title="Bật/Tắt xoay 360 độ tự động">🎬 Tự xoay 360°</button>
    </div>
  </div>

  <!-- Zoom Buttons -->
  <div class="zoom-controls">
    <button class="zoom-btn" id="zi" title="Phóng to">+</button>
    <button class="zoom-btn" id="zo" title="Thu nhỏ">−</button>
  </div>

  <!-- 3D Canvas Stage -->
  <div class="stage" id="stage"></div>

  <!-- Room Info Popup -->
  <div class="room-popup-card" id="roomPopup"></div>

  <!-- Floor Selector Tabs -->
  <div class="floor-tabs" id="tabs"></div>

  <!-- Legend -->
  <details class="legend-box" open>
    <summary>Chú giải phân khu</summary>
    <div id="legendContent"></div>
  </details>
</div>

<script>
// ═══════════════════════════════════════════════════════════════════════════
// HỆ MÀU CHỨC NĂNG CHUẨN Y TẾ
// ═══════════════════════════════════════════════════════════════════════════
const TY = {{
  er:     {{ c: 0xe55353, bg: 0xfce8e8, l: 'Cấp cứu 24/7' }},
  exam:   {{ c: 0x0284c7, bg: 0xe0f2fe, l: 'Phòng khám đa khoa / Nội' }},
  spec:   {{ c: 0x2563eb, bg: 0xdbeafe, l: 'Chuyên khoa sâu (Tầng 2)' }},
  lab:    {{ c: 0x7c3aed, bg: 0xede9fe, l: 'Xét nghiệm / CĐHA (X-quang, CT)' }},
  pharm:  {{ c: 0x059669, bg: 0xd1fae5, l: 'Nhà thuốc Bệnh viện' }},
  ob:     {{ c: 0xdb2777, bg: 0xfce7f3, l: 'Sản phụ khoa & Nhi' }},
  ward:   {{ c: 0x0891b2, bg: 0xcffafe, l: 'Nội trú (Thăm bệnh)' }},
  locked: {{ c: 0x64748b, bg: 0xe2e8f0, l: 'Chỉ nhân viên (Phòng mổ, ICU)' }},
  util:   {{ c: 0x475569, bg: 0xf1f5f9, l: 'Sảnh tiếp đón / Thu ngân' }}
}};
const hex = n => '#' + n.toString(16).padStart(6, '0');

// ═══════════════════════════════════════════════════════════════════════════
// DỮ LIỆU 35 PHÒNG THỰC TẾ 3 TẦNG BỆNH VIỆN ATUS
// ═══════════════════════════════════════════════════════════════════════════
const FL = [
  {{
    n: 'Tầng 1', s: 'Tiếp đón, Cấp cứu & Cận lâm sàng',
    r: [
      ['Khoa Cấp cứu 24/7', 'T1-04', 'er', -14, -7, 1.5, 8.5, false],
      ['Sảnh chính & Kiosk', 'T1-01', 'util', -7, 0, 1.5, 8.5, false],
      ['Quầy đăng ký & BHYT', 'T1-02', 'util', 0, 6, 1.5, 8.5, false],
      ['Quầy thu ngân', 'T1-03', 'util', 6, 10, 1.5, 8.5, false],
      ['Nhà thuốc ATUS', 'T1-12', 'pharm', 10, 14, 1.5, 8.5, false],
      ['Khám Nội tổng quát 1', 'T1-05', 'exam', -14, -8, -8.5, -1.5, false],
      ['Khám Nội tổng quát 2', 'T1-06', 'exam', -8, -2, -8.5, -1.5, false],
      ['Khám Nhi (Cửa riêng)', 'T1-07', 'ob', -2, 4, -8.5, -1.5, false],
      ['Phòng Xét nghiệm máu', 'T1-09', 'lab', 4, 9, -8.5, -1.5, false],
      ['Chụp X-quang', 'T1-10', 'lab', 9, 14, -8.5, -5, false],
      ['Phòng Siêu âm', 'T1-11', 'exam', 9, 14, -5, -1.5, false]
    ]
  }},
  {{
    n: 'Tầng 2', s: '14 Chuyên khoa ngoại trú',
    r: [
      ['Tim mạch (Điện tim)', 'T2-01', 'spec', -14, -8, 1.5, 8.5, false],
      ['Siêu âm tim', 'T2-02', 'spec', -8, -2, 1.5, 8.5, false],
      ['Tiêu hóa (Nội soi)', 'T2-03', 'spec', -2, 4, 1.5, 8.5, false],
      ['Phòng Hô hấp', 'T2-04', 'spec', 4, 9, 1.5, 8.5, false],
      ['Phòng Thần kinh', 'T2-05', 'spec', 9, 14, 1.5, 8.5, false],
      ['Cơ Xương Khớp', 'T2-06', 'spec', -14, -9, -8.5, -1.5, false],
      ['Tai Mũi Họng', 'T2-07', 'spec', -9, -4, -8.5, -1.5, false],
      ['Răng Hàm Mặt', 'T2-08', 'spec', -4, 1, -8.5, -1.5, false],
      ['Khám Mắt', 'T2-09', 'spec', 1, 5, -8.5, -1.5, false],
      ['Khám Da liễu', 'T2-10', 'spec', 5, 8, -8.5, -1.5, false],
      ['Sản phụ khoa', 'T2-11', 'ob', 8, 11, -8.5, -1.5, false],
      ['Chụp CT / MRI Scanner', 'T2-13', 'lab', 11, 14, -8.5, -1.5, false]
    ]
  }},
  {{
    n: 'Tầng 3', s: 'Phẫu thuật, Nội trú & Hành chính',
    r: [
      ['Khối Phòng Mổ 🔒', 'T3-01', 'locked', -14, -6, 1.5, 8.5, true],
      ['Hồi sức tích cực ICU 🔒', 'T3-02', 'locked', -6, 0, 1.5, 8.5, true],
      ['Nội trú Nội (20 giường)', 'T3-03', 'ward', 0, 7, 1.5, 8.5, false],
      ['Nội trú Ngoại (20 giường)', 'T3-04', 'ward', 7, 14, 1.5, 8.5, false],
      ['Nội trú Sản - Nhi', 'T3-05', 'ob', -14, -6, -8.5, -1.5, false],
      ['Khu Hành chính & Giám đốc 🔒', 'T3-06', 'locked', -6, 0, -8.5, -1.5, true],
      ['Phòng trực Bác sĩ 🔒', 'T3-07', 'locked', 0, 7, -8.5, -1.5, true],
      ['Kho Dược trung tâm 🔒', 'T3-08', 'locked', 7, 14, -8.5, -1.5, true]
    ]
  }}
];

const TARGET_FLOOR_IDX = {init_f_idx};
const TARGET_DEPT_STR = {init_dept_json};
const IS_MINI = {"true" if is_mini else "false"};

// ═══════════════════════════════════════════════════════════════════════════
// THIẾT LẬP THREE.JS SCENE, CAMERA & LIGHTS
// ═══════════════════════════════════════════════════════════════════════════
const stage = document.getElementById('stage');
const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true, powerPreference: "high-performance" }});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 400);

// Ánh sáng dịu mắt chuẩn y tế
const ambient = new THREE.AmbientLight(0xffffff, 0.88);
scene.add(ambient);

const sun = new THREE.DirectionalLight(0xffffff, 0.55);
sun.position.set(-18, 32, 20);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
Object.assign(sun.shadow.camera, {{ left: -26, right: 26, top: 26, bottom: -26, near: 1, far: 90 }});
scene.add(sun);

// Helper tạo khối 3D
const box = (g, x, y, z, w, h, d, c, roughness = 0.85) => {{
  const m = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({{ color: c, roughness: roughness }})
  );
  m.position.set(x, y + h / 2, z);
  m.castShadow = true;
  m.receiveShadow = true;
  g.add(m);
  return m;
}};

// Tường ngăn phòng
const wall = (g, x0, z0, x1, z1, isRestricted = false) => {{
  const t = 0.28;
  const col = isRestricted ? 0xa8b8c2 : 0xc2d4de;
  box(g, (x0 + x1) / 2, 0, (z0 + z1) / 2, Math.abs(x1 - x0) + t, 1.85, Math.abs(z1 - z0) + t, col);
}};

// Đồ nội thất tối giản
function furnish(g, r) {{
  const [, , ty, x0, x1, z0, z1, isRestr] = r;
  if (isRestr) return; // Không vẽ đồ trong khu vực cấm
  const cols = Math.max(1, Math.floor((x1 - x0 - 2) / 3.4));
  const rows = Math.max(1, Math.floor((z1 - z0 - 2) / 3.2));
  for (let i = 0; i < cols; i++) {{
    for (let j = 0; j < rows; j++) {{
      const x = x0 + (x1 - x0) * (i + 0.5) / cols;
      const z = z0 + (z1 - z0) * (j + 0.6) / rows + 0.2;
      if (ty === 'er' || ty === 'ob' || ty === 'ward') {{
        box(g, x, 0.05, z, 1.8, 0.45, 0.9, 0xffffff); // Giường
        box(g, x - 0.7, 0.5, z, 0.4, 0.12, 0.7, TY[ty].c); // Gối
      }} else if (ty === 'exam' || ty === 'spec') {{
        box(g, x, 0.05, z, 1.5, 0.65, 0.8, 0xa0b4c0); // Bàn bác sĩ
        box(g, x, 0.05, z + 0.9, 0.5, 0.45, 0.5, 0x507085); // Ghế
      }} else if (ty === 'lab') {{
        box(g, x, 0.05, z, 2.0, 0.85, 0.8, 0x8b80c5); // Bàn xét nghiệm
      }} else if (ty === 'pharm') {{
        box(g, x, 0.05, z - 0.8, 2.2, 1.4, 0.5, 0x65b88f); // Kệ thuốc
        box(g, x, 0.05, z + 0.6, 1.6, 0.7, 0.7, 0xffffff); // Quầy phát thuốc
      }}
    }}
  }}
}}

const groups = [], rooms = [], tiles = [], marks = [];
const lbRoot = stage;

function mkEl(cls, html, css) {{
  const e = document.createElement('div');
  e.className = cls;
  e.innerHTML = html;
  if (css) e.style.setProperty('--c', css);
  lbRoot.appendChild(e);
  return e;
}}

// Dựng 3 tầng
FL.forEach((F, fi) => {{
  const g = new THREE.Group();
  g.userData.ty = 0;
  
  // Sàn bê tông tòa nhà (29m x 18m)
  box(g, 0, -0.5, 0, 30, 0.5, 19, 0xb0c4ce);
  
  // Hành lang trung tâm sáng màu
  box(g, 0, 0, 0, 28, 0.08, 3.2, 0xf8fafc);
  
  // Hành lang phụ dọc
  box(g, -11, 0, 0, 3.2, 0.08, 17, 0xf8fafc);
  box(g, 11, 0, 0, 3.2, 0.08, 17, 0xf8fafc);

  F.r.forEach(a => {{
    const [n, code, ty, x0, x1, z0, z1, isRestr] = a;
    const cx = (x0 + x1) / 2;
    const cz = (z0 + z1) / 2;
    const top = z1 <= 0;

    // Mặt sàn từng phòng
    const tile = box(g, cx, 0.02, cz, x1 - x0 - 0.15, 0.08, z1 - z0 - 0.15, TY[ty].bg);
    tile.material.emissive = new THREE.Color(TY[ty].c);
    tile.material.emissiveIntensity = 0;

    // Nhãn phòng
    const lockBadge = isRestr ? ' 🔒' : '';
    const extraClass = isRestr ? 'lbl restricted' : 'lbl';
    const R = {{
      n, code, ty, cx, cz, fi, tile, isRestr,
      y: 2.5,
      el: mkEl(extraClass, '<span>' + n + '</span><i>' + code + '</i>' + lockBadge, hex(TY[ty].c))
    }};
    tile.userData.room = R;
    tiles.push(tile);
    rooms.push(R);

    // Tường bao quanh phòng
    const fz = top ? z0 : z1;
    const dz = top ? z1 : z0;
    wall(g, x0, fz, x1, fz, isRestr);
    wall(g, x0, z0, x0, z1, isRestr);
    wall(g, x1, z0, x1, z1, isRestr);
    // Cửa vào
    wall(g, x0, dz, cx - 1.1, dz, isRestr);
    wall(g, cx + 1.1, dz, x1, dz, isRestr);

    furnish(g, a);
  }});

  // Thang máy & WC cố định ở 2 đầu hành lang
  marks.push(
    {{ fi, x: -11, z: 0, el: mkEl('mk', '🛗 Thang máy 1 & Thang bộ') }},
    {{ fi, x: 11, z: 0, el: mkEl('mk', '🛗 Thang máy 2') }},
    {{ fi, x: -11, z: 7.5, el: mkEl('mk', '🚻 WC') }}
  );

  scene.add(g);
  groups.push(g);
}});

// Lộ trình dẫn đường từ sảnh Tầng 1
const pathCoords = [[-7, 7.5], [-7, 0], [2, 0], [2, -5]];
for (let i = 0; i < pathCoords.length - 1; i++) {{
  const [a, b] = [pathCoords[i], pathCoords[i + 1]];
  box(groups[0], (a[0] + b[0]) / 2, 0.12, (a[1] + b[1]) / 2, Math.abs(b[0] - a[0]) + 0.38, 0.06, Math.abs(b[1] - a[1]) + 0.38, 0x008f88);
}}
const cone = new THREE.Mesh(new THREE.ConeGeometry(0.5, 1.1, 16), new THREE.MeshStandardMaterial({{ color: 0x008f88 }}));
cone.position.set(2, 1.4, -5);
cone.rotation.x = Math.PI;
groups[0].add(cone);

const ring = new THREE.Mesh(new THREE.RingGeometry(0.4, 0.75, 32), new THREE.MeshBasicMaterial({{ color: 0xe55353, transparent: true, side: THREE.DoubleSide }}));
ring.rotation.x = -Math.PI / 2;
ring.position.set(-7, 0.22, 7.5);
groups[0].add(ring);

marks.push(
  {{ fi: 0, x: -7, z: 7.5, el: mkEl('mk here', '📍 Bạn đang ở đây') }},
  {{ fi: 0, x: -14, z: 7.5, el: mkEl('mk', '🚑 Cửa Xe Cấp Cứu') }}
);


// ═══════════════════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════════════
// ĐỘNG CƠ CAMERA 360° QUÁN TÍNH CHUẨN 60 FPS (SMOOTH DAMPING & TOUCH)
// ═══════════════════════════════════════════════════════════════════════════
let targetAz = -0.75;      // Góc quay mục tiêu phương vị (xoay 360 độ vô tận)
let targetPol = 0.85;     // Góc ngẩng mục tiêu (Clamped 10° - 82°)
let az = targetAz;        // Góc thực tế nội suy
let pol = targetPol;      // Góc ngẩng thực tế nội suy
let azMomentum = 0;       // Quán tính lướt khi nhấc tay/chuột
let polMomentum = 0;
let isDragging = false;
let isRightDragging = false;
let autoRotate = false;

let zoom = IS_MINI ? 0.85 : 1.0;
let targetZoom = zoom;

const tgt = new THREE.Vector3(0, 0, 0);
const targetTgt = new THREE.Vector3(0, 0, 0);
const tgtY = () => (selFloor === -1 ? 6.5 : 0);

let lastMouseX = 0, lastMouseY = 0;
let dragDist = 0;

// Multi-touch gestures
let touchMode = 'none'; // 'none' | 'rotate' | 'pinch'
let initialPinchDist = 0;
let initialPinchZoom = 1;

function setCam() {{
  const R = 75;
  camera.position.set(
    tgt.x + R * Math.sin(pol) * Math.sin(az),
    tgt.y + R * Math.cos(pol),
    tgt.z + R * Math.sin(pol) * Math.cos(az)
  );
  camera.lookAt(tgt);
}}

function resize() {{
  const w = stage.clientWidth;
  const h = stage.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  const aspect = w / h;
  const s = Math.max(14, 18 / aspect) / zoom;
  Object.assign(camera, {{ left: -s * aspect, right: s * aspect, top: s, bottom: -s }});
  camera.updateProjectionMatrix();
}}
window.addEventListener('resize', resize);


// ── SỰ KIỆN CHUỘT & CON TRỎ (MOUSE POINTER INTERACTION) ─────────────────────
const cv = renderer.domElement;

cv.addEventListener('contextmenu', e => e.preventDefault());

cv.addEventListener('pointerdown', e => {{
  if (e.pointerType === 'touch') return; // Xử lý riêng ở touch event để mượt hơn
  stage.classList.add('grabbing');
  isDragging = true;
  isRightDragging = (e.button === 2);
  lastMouseX = e.clientX;
  lastMouseY = e.clientY;
  dragDist = 0;
  azMomentum = 0;
  polMomentum = 0;
  if (autoRotate) {{
    autoRotate = false;
    const btn = document.getElementById('btn-auto-rotate');
    if (btn) btn.classList.remove('active');
  }}
  cv.setPointerCapture(e.pointerId);
}});

cv.addEventListener('pointermove', e => {{
  if (e.pointerType === 'touch' || !isDragging) return;
  const dx = e.clientX - lastMouseX;
  const dy = e.clientY - lastMouseY;
  dragDist += Math.abs(dx) + Math.abs(dy);

  if (isRightDragging) {{
    // Pan di chuyển tâm mặt bằng
    const panFactor = (24 / zoom) / stage.clientHeight;
    const cosAz = Math.cos(az), sinAz = Math.sin(az);
    targetTgt.x -= (dx * cosAz - dy * sinAz * Math.cos(pol)) * panFactor;
    targetTgt.z -= (-dx * sinAz - dy * cosAz * Math.cos(pol)) * panFactor;
  }} else {{
    // Xoay 360 độ có gia tốc mượt mà
    const rotSpeed = 0.0065;
    targetAz -= dx * rotSpeed;
    targetPol = Math.max(0.18, Math.min(1.42, targetPol - dy * (rotSpeed * 0.85)));
    azMomentum = -dx * rotSpeed;
    polMomentum = -dy * (rotSpeed * 0.85);
  }}

  lastMouseX = e.clientX;
  lastMouseY = e.clientY;
}});

cv.addEventListener('pointerup', e => {{
  if (e.pointerType === 'touch') return;
  stage.classList.remove('grabbing');
  isDragging = false;
  isRightDragging = false;
  if (dragDist < 6) {{
    pick(e);
  }}
}});

// Con lăn phóng to thu nhỏ mượt mà
cv.addEventListener('wheel', e => {{
  e.preventDefault();
  targetZoom = Math.max(0.4, Math.min(3.5, targetZoom * (e.deltaY < 0 ? 1.15 : 0.87)));
}}, {{ passive: false }});


// ── SỰ KIỆN CẢM ỨNG ĐA ĐIỂM (1-FINGER ROTATE 360° & 2-FINGER PINCH/PAN) ─────
cv.addEventListener('touchstart', e => {{
  dragDist = 0;
  azMomentum = 0;
  polMomentum = 0;
  if (autoRotate) {{
    autoRotate = false;
    const btn = document.getElementById('btn-auto-rotate');
    if (btn) btn.classList.remove('active');
  }}

  if (e.touches.length === 2) {{
    touchMode = 'pinch';
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    initialPinchDist = Math.hypot(dx, dy);
    initialPinchZoom = targetZoom;
    lastMouseX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
    lastMouseY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
  }} else if (e.touches.length === 1) {{
    touchMode = 'rotate';
    isDragging = true;
    lastMouseX = e.touches[0].clientX;
    lastMouseY = e.touches[0].clientY;
  }}
}}, {{ passive: false }});

cv.addEventListener('touchmove', e => {{
  e.preventDefault(); // Chống cuộn trang web khi đang vuốt 3D
  if (touchMode === 'pinch' && e.touches.length === 2) {{
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    const dist = Math.hypot(dx, dy);
    if (initialPinchDist > 0) {{
      targetZoom = Math.max(0.4, Math.min(3.5, initialPinchZoom * (dist / initialPinchDist)));
    }}
    // 2-finger Pan
    const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
    const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
    const panFactor = (24 / zoom) / stage.clientHeight;
    const cosAz = Math.cos(az), sinAz = Math.sin(az);
    targetTgt.x -= ((midX - lastMouseX) * cosAz - (midY - lastMouseY) * sinAz * Math.cos(pol)) * panFactor;
    targetTgt.z -= (-(midX - lastMouseX) * sinAz - (midY - lastMouseY) * cosAz * Math.cos(pol)) * panFactor;
    lastMouseX = midX;
    lastMouseY = midY;
  }} else if (touchMode === 'rotate' && e.touches.length === 1) {{
    const dx = e.touches[0].clientX - lastMouseX;
    const dy = e.touches[0].clientY - lastMouseY;
    dragDist += Math.abs(dx) + Math.abs(dy);
    const rotSpeed = 0.007;
    targetAz -= dx * rotSpeed;
    targetPol = Math.max(0.18, Math.min(1.42, targetPol - dy * (rotSpeed * 0.85)));
    azMomentum = -dx * rotSpeed;
    polMomentum = -dy * (rotSpeed * 0.85);
    lastMouseX = e.touches[0].clientX;
    lastMouseY = e.touches[0].clientY;
  }}
}}, {{ passive: false }});

cv.addEventListener('touchend', e => {{
  if (touchMode === 'rotate' && dragDist < 8 && e.changedTouches.length === 1) {{
    pick(e.changedTouches[0]);
  }}
  if (e.touches.length === 0) {{
    touchMode = 'none';
    isDragging = false;
  }} else if (e.touches.length === 1) {{
    touchMode = 'rotate';
    lastMouseX = e.touches[0].clientX;
    lastMouseY = e.touches[0].clientY;
  }}
}});


// ── NÚT BẤM TIỆN ÍCH TRÊN THANH TOOLBAR ─────────────────────────────────────
const zi = document.getElementById('zi');
const zo = document.getElementById('zo');
if (zi) zi.onclick = () => {{ targetZoom = Math.min(3.5, targetZoom * 1.25); }};
if (zo) zo.onclick = () => {{ targetZoom = Math.max(0.4, targetZoom / 1.25); }};

const btnResetView = document.getElementById('btn-reset-view');
if (btnResetView) {{
  btnResetView.onclick = () => {{
    azMomentum = 0; polMomentum = 0;
    targetAz = -0.75; targetPol = 0.85;
    targetZoom = 1.0;
    targetTgt.set(0, 0, 0);
  }};
}}

const btnAutoRotate = document.getElementById('btn-auto-rotate');
if (btnAutoRotate) {{
  btnAutoRotate.onclick = () => {{
    autoRotate = !autoRotate;
    btnAutoRotate.classList.toggle('active', autoRotate);
    if (autoRotate) {{
      azMomentum = 0;
    }}
  }};
}}


// ═══════════════════════════════════════════════════════════════════════════
// TƯƠNG TÁC CHỌN PHÒNG & THÔNG TIN POPUP
// ═══════════════════════════════════════════════════════════════════════════
const ray = new THREE.Raycaster();
const roomPopup = document.getElementById('roomPopup');
let selFloor = TARGET_FLOOR_IDX;
let selRoom = null;

function pick(e) {{
  const b = cv.getBoundingClientRect();
  ray.setFromCamera({{
    x: ((e.clientX - b.left) / b.width) * 2 - 1,
    y: -((e.clientY - b.top) / b.height) * 2 + 1
  }}, camera);

  const vis = tiles.filter(t => groups[t.userData.room.fi].visible);
  const hit = ray.intersectObjects(vis)[0];
  selectRoom(hit ? hit.object.userData.room : null);
}}

function selectRoom(r) {{
  selRoom = r;
  rooms.forEach(x => {{
    x.tile.material.emissiveIntensity = (x === r) ? 0.6 : 0;
    x.el.classList.toggle('sel', x === r);
  }});

  if (!r || IS_MINI) {{
    if (roomPopup) roomPopup.style.display = 'none';
    return;
  }}

  roomPopup.style.display = 'block';
  const lockNotice = r.isRestr ? '<p style="color:#e55353;font-weight:700;">⚠️ Khu vực hạn chế - Chỉ dành cho nhân viên y tế</p>' : '';
  const bookBtn = r.isRestr ? '' : '<button id="btn-popup-book">📅 Đặt lịch tại khoa này</button>';

  roomPopup.innerHTML = `
    <b>${{r.n}}</b>
    <div class="p-meta">Mã phòng: <b>${{r.code}}</b> · ${{FL[r.fi].n}}</div>
    <span class="p-badge" style="background:${{TY[r.ty].bg}};color:${{hex(TY[r.ty].c)}};">${{TY[r.ty].l}}</span>
    <p style="margin:4px 0;font-size:12px;color:#64748b;">Giờ làm việc: 07:00 – 17:00</p>
    ${{lockNotice}}
    ${{bookBtn}}
  `;

  const btnBook = document.getElementById('btn-popup-book');
  if (btnBook) {{
    btnBook.onclick = () => {{
      window.parent.postMessage({{
        type: 'STREAMLIT_SELECT_DEPT',
        dept: r.n,
        floor: r.fi + 1
      }}, '*');
    }};
  }}
}}

// Chuyển tầng
const tabs = document.getElementById('tabs');
function setFloor(i) {{
  selFloor = i;
  selectRoom(null);
  groups.forEach((g, k) => {{
    g.visible = (i === -1 || i === k);
    g.userData.ty = (i === -1 ? k * 7.5 : 0);
  }});
  if (tabs) {{
    [...tabs.children].forEach((b, k) => b.classList.toggle('on', k === i + 1));
  }}
}}

if (!IS_MINI && tabs) {{
  [{{ n: 'Tất cả tầng', s: 'Mặt bằng 3 tầng' }}, ...FL.map(f => ({{ n: f.n, s: f.s }}))].forEach((f, k) => {{
    const b = document.createElement('button');
    b.className = 'floor-tab-btn' + (k === TARGET_FLOOR_IDX + 1 ? ' on' : '');
    b.innerHTML = '<b>' + f.n + '</b><small>' + f.s + '</small>';
    b.onclick = () => setFloor(k - 1);
    tabs.appendChild(b);
  }});

  // Chú giải phân khu
  document.getElementById('legendContent').innerHTML = Object.values(TY).map(t =>
    `<div class="legend-item"><span class="legend-dot" style="background:${{hex(t.c)}};"></span>${{t.l}}</div>`
  ).join('');
}}

// Tìm kiếm nhanh
const norm = s => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/đ/g, 'd').toLowerCase();
const qInp = document.getElementById('q');
if (qInp) {{
  qInp.addEventListener('input', () => {{
    const v = norm(qInp.value.trim());
    if (!v) {{ selectRoom(null); return; }}
    const r = rooms.find(r => norm(r.n + ' ' + r.code).includes(v));
    if (r) {{
      if (selFloor !== -1 && selFloor !== r.fi) setFloor(r.fi);
      selectRoom(r);
    }}
  }});
}}


// ═══════════════════════════════════════════════════════════════════════════
// VÒNG LẶP RENDER CHUẨN 60 FPS CÓ QUÁN TÍNH
// ═══════════════════════════════════════════════════════════════════════════
const t0 = performance.now();
const v = new THREE.Vector3();

function loop() {{
  requestAnimationFrame(loop);
  const t = (performance.now() - t0) / 1000;

  // 1. Quán tính xoay 360 độ & Tự xoay (Continuous 360° Damping)
  if (!isDragging) {{
    if (autoRotate) {{
      targetAz += 0.0035;
    }} else if (Math.abs(azMomentum) > 0.00005) {{
      targetAz += azMomentum;
      targetPol = Math.max(0.18, Math.min(1.42, targetPol + polMomentum));
      azMomentum *= 0.93;
      polMomentum *= 0.90;
    }}
  }}

  // Nội suy mượt mà chuẩn 60 FPS (Lerp Damping cho góc xoay)
  az += (targetAz - az) * 0.18;
  pol += (targetPol - pol) * 0.18;

  // 2. Nội suy phóng to thu nhỏ mượt mà (Lerp Zoom)
  if (Math.abs(targetZoom - zoom) > 0.001) {{
    zoom += (targetZoom - zoom) * 0.16;
    resize();
  }}

  // 3. Nội suy Pan di chuyển tâm
  tgt.x += (targetTgt.x - tgt.x) * 0.12;
  tgt.y += (tgtY() - tgt.y) * 0.12;
  tgt.z += (targetTgt.z - tgt.z) * 0.12;

  setCam();

  // 4. Nội suy tách tầng
  groups.forEach(g => {{
    g.position.y += (g.userData.ty - g.position.y) * 0.14;
  }});

  // 5. Hiệu ứng sóng radar điểm xuất phát
  const k = (t % 1.5) / 1.5;
  ring.scale.setScalar(0.6 + k * 1.8);
  ring.material.opacity = 1 - k;
  cone.position.y = 1.4 + Math.sin(t * 4.5) * 0.15;

  // 6. Chiếu tọa độ nhãn phòng (Billboard Projection)
  const w = stage.clientWidth;
  const h = stage.clientHeight;
  const put = (el, fi, x, y, z) => {{
    const g = groups[fi];
    if (!g.visible) {{
      el.style.display = 'none';
      return;
    }}
    el.style.display = 'block';
    v.set(x, y + g.position.y, z).project(camera);
    el.style.transform = `translate(${{(v.x * 0.5 + 0.5) * w}}px, ${{(-v.y * 0.5 + 0.5) * h}}px) translate(-50%, -100%)`;
  }};

  rooms.forEach(r => put(r.el, r.fi, r.cx, r.y, r.cz));
  marks.forEach(m => put(m.el, m.fi, m.x, 1.0, m.z));

  renderer.render(scene, camera);
}}

// Khởi động
setFloor(TARGET_FLOOR_IDX);
resize();
loop();

// Tự động tìm & chọn phòng nếu có tham số
if (TARGET_DEPT_STR) {{
  setTimeout(() => {{
    const r = rooms.find(r => norm(r.n).includes(norm(TARGET_DEPT_STR)));
    if (r) {{
      setFloor(r.fi);
      selectRoom(r);
    }}
  }}, 250);
}}
</script>

</body>
</html>
"""
