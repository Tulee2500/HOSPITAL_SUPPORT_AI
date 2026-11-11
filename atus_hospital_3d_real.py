"""Mô hình 3D Bệnh Viện Isometric Đa Tầng cao cấp (Three.js Orthographic WebGL).
Khắc phục triệt để:
1. Phân biệt rõ đường đi (Hành lang & Lộ trình Wayfinding):
   - Thay đường line 1px mảnh (dễ mất hình trên Windows/WebGL) bằng dải ruy-băng 3D Ribbon phẳng (bề rộng 0.4m)
     phát sáng màu Cyan ngọc (#008f88 / #00b4d8) với các vòng tròn waypoint nổi bật, nhìn thấy rõ 100%.
   - Mặt sàn hành lang màu trắng sáng (#ffffff) có viền tương phản với nền sàn các phòng khám,
     giúp phân biệt rõ ràng lối đi, cửa vào và từng phân khu.
2. Tinh chỉnh kích thước nhãn phòng (Compact Pill Badges):
   - Giảm kích thước nhãn vừa vặn chuẩn tỉ lệ (font 10px, padding 3px 8px), không còn to quá khổ,
     không che khuất xe cứu thương hay thiết bị phòng khám.
3. Độ tương phản & Màu sắc chuẩn thiết kế y tế:
   - Nền canvas xung quanh: Màu ngọc nhạt dịu mắt (#edf6f6) làm nổi bật khối sa bàn 3D màu trắng.
   - Sàn từng khoa phòng mang màu sắc tươi sáng, phân biệt rõ ràng:
       + Cấp cứu: Hồng san hô (#fda4af)
       + Khám bệnh: Xanh mint (#a7f3d0)
       + Khoa Nội: Xanh dương (#93c5fd)
       + Khoa Ngoại: Xám vô trùng (#cbd5e1)
       + Xét nghiệm: Tím lavender (#c4b5fd)
       + Nhà thuốc: Xanh ngọc (#6ee7b7)
4. Chuẩn hóa 100% dữ liệu phòng theo Database SQL Server:
   - Tầng 1: Cấp cứu 24/7 (P.101), Khám bệnh, Khoa Nội (P.301 đón tiếp), Khoa Ngoại, Xét nghiệm (P.201), Nhà thuốc.
   - Tầng 2: Cận lâm sàng (P.201 Lấy máu/XN, P.202 Đo hô hấp, P.203 X-Quang, P.204 MRI/CT).
   - Tầng 3: Chuyên khoa (P.301 Nội, P.302 Mắt, P.303 Tai Mũi Họng, P.304 Răng Hàm Mặt, P.305 Da Liễu).
   - Tầng 4: Sản (P.401) & Nhi (P.402).
"""
from __future__ import annotations

import json


def get_hospital_3d_html(target_floor=1, target_dept=""):
    """Trả về HTML Three.js mặt bằng Isometric hiển thị đường đi và khoa phòng cực kỳ rõ ràng."""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
        body {{
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: #edf6f6;
        }}
        #viewport {{
            width: 100%; height: 610px; position: relative;
            background: radial-gradient(circle at 50% 45%, #ffffff 0%, #edf6f6 80%, #e2f1f0 100%);
            border-radius: 14px; overflow: hidden;
            border: 1px solid #cbd5e1;
            box-shadow: 0 4px 20px rgba(0, 58, 112, 0.06);
        }}

        /* Thanh tiêu đề trên cùng */
        .map-top-bar {{
            position: absolute; top: 12px; left: 16px; right: 16px;
            display: flex; justify-content: space-between; align-items: center;
            z-index: 30; pointer-events: none;
        }}
        .map-top-title {{
            font-size: 1.1rem; font-weight: 800; color: #003a70;
            letter-spacing: 0.5px; text-transform: uppercase;
        }}
        .booking-cta-btn {{
            pointer-events: auto;
            background: #008f88; color: #ffffff; border: none;
            padding: 7px 15px; border-radius: 8px; font-weight: 700; font-size: 12px;
            display: flex; align-items: center; gap: 6px; cursor: pointer;
            box-shadow: 0 2px 8px rgba(0, 143, 136, 0.35);
            transition: all 0.2s ease;
        }}
        .booking-cta-btn:hover {{
            background: #007670; transform: translateY(-1px);
        }}

        /* Cụm chuyển tầng ở giữa dưới */
        .floor-switcher {{
            position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%);
            display: flex; gap: 6px; z-index: 30;
            background: #ffffff; padding: 4px 6px;
            border-radius: 10px; box-shadow: 0 4px 16px rgba(0, 58, 112, 0.12);
            border: 1px solid #cbd5e1;
        }}
        .floor-btn {{
            border: none; background: transparent; color: #334155;
            padding: 6px 14px; border-radius: 7px; font-weight: 700; font-size: 12.5px;
            cursor: pointer; transition: all 0.2s ease;
        }}
        .floor-btn:hover {{ background: #f1f5f9; }}
        .floor-btn.active {{
            background: #008f88; color: #ffffff;
            box-shadow: 0 2px 8px rgba(0, 143, 136, 0.35);
        }}

        /* Cụm Zoom controls góc trái dưới */
        .zoom-controls {{
            position: absolute; bottom: 14px; left: 14px;
            display: flex; flex-direction: column; align-items: center; gap: 2px; z-index: 30;
            background: #ffffff; padding: 4px;
            border-radius: 8px; box-shadow: 0 4px 14px rgba(0, 58, 112, 0.1);
            border: 1px solid #cbd5e1;
        }}
        .zoom-btn {{
            width: 28px; height: 28px; border: none; background: #f8fafc;
            color: #0f172a; font-size: 15px; font-weight: 700;
            border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center;
            transition: 0.15s;
        }}
        .zoom-btn:hover {{ background: #008f88; color: #ffffff; }}
        .zoom-lbl {{ font-size: 8.5px; font-weight: 700; color: #64748b; margin: 1px 0; text-transform: uppercase; }}

        /* Nhãn phòng khám 3D HTML Overlay - GỌN GÀNG, KHÔNG CHE KHUẤT */
        .room-tag {{
            position: absolute; transform: translate(-50%, -50%);
            padding: 3px 9px; border-radius: 5px; font-size: 10.5px; font-weight: 800;
            white-space: nowrap; pointer-events: none; z-index: 20;
            box-shadow: 0 2px 8px rgba(0, 30, 60, 0.22);
            transition: transform 0.2s, opacity 0.2s;
            border: 1px solid #ffffff;
        }}
        .tag-emergency {{ background: #ef4444; color: #ffffff; }}
        .tag-primary-blue {{ background: #0284c7; color: #ffffff; }}
        .tag-dark-blue {{ background: #0369a1; color: #ffffff; }}
        .tag-pharmacy {{ background: #059669; color: #ffffff; }}
        .tag-lab {{ background: #7c3aed; color: #ffffff; }}

        /* Icon tiện ích phụ thu nhỏ */
        .icon-tag {{
            position: absolute; transform: translate(-50%, -50%);
            width: 20px; height: 20px; border-radius: 4px;
            display: flex; align-items: center; justify-content: center;
            font-size: 10.5px; z-index: 18; pointer-events: none;
            box-shadow: 0 1px 4px rgba(0,0,0,0.18);
            border: 1px solid #ffffff;
        }}
        .icon-restroom {{ background: #0284c7; color: #ffffff; }}
        .icon-elevator {{ background: #0369a1; color: #ffffff; }}
        .icon-heart {{ background: #ef4444; color: #ffffff; border-radius: 50%; width: 18px; height: 18px; }}

        /* Nhãn văn bản dán sàn */
        .floor-text-label {{
            position: absolute; transform: translate(-50%, -50%);
            font-size: 9.5px; font-weight: 800; color: #003a70;
            background: rgba(255, 255, 255, 0.95); padding: 2px 6px;
            border-radius: 3px; border: 1px solid #008f88;
            pointer-events: none; z-index: 15; white-space: nowrap;
        }}

        /* Nhãn phòng AI đang chọn (Nhấp nháy nổi bật) */
        .tag-highlight {{
            background: #f43f5e !important; color: #ffffff !important;
            border: 2px solid #ffffff !important; font-size: 12px !important;
            padding: 5px 12px !important;
            box-shadow: 0 0 20px rgba(244, 63, 94, 0.9), 0 4px 10px rgba(0,0,0,0.3) !important;
            animation: pulse-tag 1.2s infinite alternate !important;
            z-index: 25 !important;
        }}
        @keyframes pulse-tag {{
            0% {{ transform: translate(-50%, -50%) scale(1); }}
            100% {{ transform: translate(-50%, -50%) scale(1.12); }}
        }}
    </style>
</head>
<body>
    <div id="viewport">
        <!-- Top bar -->
        <div class="map-top-bar">
            <div class="map-top-title">BẢN ĐỒ BỆNH VIỆN ATUS 3D</div>
            <button class="booking-cta-btn" onclick="triggerBooking()">
                <span>📅</span> <span>ĐẶT LỊCH KHÁM</span>
            </button>
        </div>

        <!-- Zoom Controls -->
        <div class="zoom-controls">
            <button class="zoom-btn" onclick="zoomIn()" title="Phóng to">+</button>
            <span class="zoom-lbl">Zoom</span>
            <button class="zoom-btn" onclick="zoomOut()" title="Thu nhỏ">−</button>
        </div>

        <!-- Chuyển tầng -->
        <div class="floor-switcher">
            <button class="floor-btn" id="fbtn-1" onclick="switchFloor(1)">Tầng 1 (Tiếp Đón/Cấp Cứu)</button>
            <button class="floor-btn" id="fbtn-2" onclick="switchFloor(2)">Tầng 2 (Cận Lâm Sàng)</button>
            <button class="floor-btn" id="fbtn-3" onclick="switchFloor(3)">Tầng 3 (Chuyên Khoa)</button>
            <button class="floor-btn" id="fbtn-4" onclick="switchFloor(4)">Tầng 4 (Sản/Nhi)</button>
        </div>

        <div id="labels-container"></div>
    </div>

    <!-- Three.js + OrbitControls -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>

    <script>
        const TARGET_FLOOR = {int(target_floor) if target_floor else 1};
        const TARGET_DEPT = {json.dumps(target_dept, ensure_ascii=False)};

        const container = document.getElementById('viewport');
        const labelsContainer = document.getElementById('labels-container');

        // Scene
        const scene = new THREE.Scene();

        // ORTHOGRAPHIC ISOMETRIC CAMERA (CHUẨN GÓC 45 ĐỘ HÌNH THOI CHÍNH XÁC NHƯ MOCKUP)
        const aspect = container.clientWidth / container.clientHeight;
        const frustumSize = 38;
        const camera = new THREE.OrthographicCamera(
            -frustumSize * aspect / 2,
             frustumSize * aspect / 2,
             frustumSize / 2,
            -frustumSize / 2,
            0.1, 1000
        );

        // Góc nhìn Isometric cao 48 độ từ góc trước-phải
        camera.position.set(42, 48, 42);
        camera.lookAt(0, 0, 0);

        // Renderer
        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true, powerPreference: "high-performance" }});
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        // Controls
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.target.set(0, 0, 0);
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.maxPolarAngle = Math.PI / 2.25;
        controls.minPolarAngle = Math.PI / 4.5;

        // Ánh sáng Studio trong trẻo
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.88);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffff, 0.8);
        sunLight.position.set(40, 65, 35);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 2048;
        sunLight.shadow.mapSize.height = 2048;
        sunLight.shadow.camera.left = -24;
        sunLight.shadow.camera.right = 24;
        sunLight.shadow.camera.top = 24;
        sunLight.shadow.camera.bottom = -24;
        sunLight.shadow.bias = -0.0003;
        scene.add(sunLight);

        const skyFill = new THREE.DirectionalLight(0xf0fdfa, 0.45);
        skyFill.position.set(-35, 35, -30);
        scene.add(skyFill);

        // ==========================================
        // VẬT LIỆU TƯƠNG PHẢN CAO - PHÂN BIỆT RÕ RÀNG
        // ==========================================
        const mats = {{
            // Khối đế sa bàn nổi lên trên nền
            podiumSlab: new THREE.MeshStandardMaterial({{ color: 0xcbe3e2, roughness: 0.35 }}),
            // Sàn hành lang đi lại: TRẮNG SÁNG CÓ VIỀN RÕ RÀNG
            corridorFloor: new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.2 }}),
            // Dải ruy băng đường đi Wayfinding: CYAN NEON PHÁT SÁNG NỔI BẬT
            pathRibbon: new THREE.MeshBasicMaterial({{ color: 0x008f88, side: THREE.DoubleSide }}),
            pathNodeRing: new THREE.MeshBasicMaterial({{ color: 0x008f88, side: THREE.DoubleSide }}),
            pathNodeDot: new THREE.MeshBasicMaterial({{ color: 0xffffff, side: THREE.DoubleSide }}),

            // Tường: TƯỜNG DÀY DẶN CÓ ĐỘ SÂU (Màu trắng ngà viền xanh nhạt)
            outerWall: new THREE.MeshStandardMaterial({{ color: 0xd8e8e7, roughness: 0.3 }}),
            innerWall: new THREE.MeshStandardMaterial({{ color: 0xb5dcd8, roughness: 0.35 }}),
            wallTopCap: new THREE.MeshStandardMaterial({{ color: 0x82c4bd, roughness: 0.3 }}),
            glassWindow: new THREE.MeshStandardMaterial({{ color: 0x38bdf8, roughness: 0.1, transparent: true, opacity: 0.65 }}),
            canopyTeal: new THREE.MeshStandardMaterial({{ color: 0x008f88, roughness: 0.2 }}),

            // SÀN TỪNG KHOA PHÒNG PHÂN BIỆT MÀU RÕ RÀNG:
            floorEmergency: new THREE.MeshStandardMaterial({{ color: 0xfecdd3, roughness: 0.3 }}), // Hồng đỏ Cấp cứu
            wallEmergency: new THREE.MeshStandardMaterial({{ color: 0xfca5a5, roughness: 0.35 }}),
            floorClinic: new THREE.MeshStandardMaterial({{ color: 0xa7f3d0, roughness: 0.3 }}),     // Xanh mint Khám bệnh
            floorInternal: new THREE.MeshStandardMaterial({{ color: 0xbae6fd, roughness: 0.3 }}),   // Xanh da trời Khoa Nội
            floorSurgery: new THREE.MeshStandardMaterial({{ color: 0xe2e8f0, roughness: 0.25 }}),   // Xám vô trùng Ngoại
            floorLab: new THREE.MeshStandardMaterial({{ color: 0xddd6fe, roughness: 0.3 }}),       // Tím nhạt Xét nghiệm
            floorPharmacy: new THREE.MeshStandardMaterial({{ color: 0x99f6e4, roughness: 0.3 }}),  // Xanh ngọc Nhà thuốc

            // ĐỒ ĐẠC Y TẾ:
            bedMattress: new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.3 }}),
            bedSheet: new THREE.MeshStandardMaterial({{ color: 0x0284c7, roughness: 0.3 }}),
            metalChrome: new THREE.MeshStandardMaterial({{ color: 0x94a3b8, metalness: 0.8, roughness: 0.2 }}),
            ambulanceWhite: new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.1 }}),
            ambulanceRed: new THREE.MeshStandardMaterial({{ color: 0xef4444, roughness: 0.2 }}),
            plantGreen: new THREE.MeshStandardMaterial({{ color: 0x10b981, roughness: 0.5 }}),
            potBrown: new THREE.MeshStandardMaterial({{ color: 0xd97706, roughness: 0.4 }}),
            deskWood: new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.2 }}),
            chairBlue: new THREE.MeshStandardMaterial({{ color: 0x0284c7, roughness: 0.3 }}),
            pcBlack: new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.2 }}),
            shelfWood: new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.3 }})
        }};

        let activeFloorGroup = null;
        let activeTags = [];

        function createBox(w, h, d, mat, x, y, z, rx=0, ry=0, rz=0) {{
            const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
            mesh.position.set(x, y, z);
            if (rx || ry || rz) mesh.rotation.set(rx, ry, rz);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            return mesh;
        }}

        // Helper tạo tường có độ dày & phào chỉ mép trên rõ nét
        function createWall(w, h, d, x, y, z, isInner=true) {{
            const group = new THREE.Group();
            const wallMesh = createBox(w, h, d, isInner ? mats.innerWall : mats.outerWall, 0, 0, 0);
            group.add(wallMesh);
            // Phào chỉ nẹp trên nóc tường tạo đường nét kiến trúc sắc sảo
            const cap = createBox(w * 1.02, 0.08, d * 1.02, mats.wallTopCap, 0, h/2 + 0.04, 0);
            group.add(cap);
            group.position.set(x, y, z);
            return group;
        }}

        // Helper tạo dải ruy băng đường đi Wayfinding Path 3D Ribbon (Bề rộng 0.35m - CỰC RÕ RÀNG)
        function createRibbonPathSegment(x1, z1, x2, z2, width=0.36) {{
            const dx = x2 - x1;
            const dz = z2 - z1;
            const len = Math.sqrt(dx*dx + dz*dz);
            const angle = Math.atan2(dx, dz);
            
            const seg = new THREE.Mesh(new THREE.PlaneGeometry(width, len), mats.pathRibbon);
            seg.rotation.x = -Math.PI / 2;
            seg.rotation.z = angle;
            seg.position.set((x1 + x2)/2, 0.06, (z1 + z2)/2);
            return seg;
        }}

        function createWaypointNode(x, z, radius=0.45, isStart=false) {{
            const nodeGroup = new THREE.Group();
            // Vòng tròn ngoài màu teal
            const ring = new THREE.Mesh(new THREE.CircleGeometry(radius, 24), mats.pathNodeRing);
            ring.rotation.x = -Math.PI / 2;
            ring.position.set(0, 0.07, 0);
            nodeGroup.add(ring);

            // Điểm lõi bên trong màu trắng
            const dot = new THREE.Mesh(new THREE.CircleGeometry(radius * 0.5, 24), mats.pathNodeDot);
            dot.rotation.x = -Math.PI / 2;
            dot.position.set(0, 0.08, 0);
            nodeGroup.add(dot);

            nodeGroup.position.set(x, 0, z);
            return nodeGroup;
        }}

        // Giường bệnh viện
        function createHospitalBed(x, z, rot=0) {{
            const bed = new THREE.Group();
            bed.add(createBox(1.2, 0.35, 2.0, mats.metalChrome, 0, 0.18, 0));
            bed.add(createBox(1.1, 0.18, 1.9, mats.bedMattress, 0, 0.44, 0));
            bed.add(createBox(1.12, 0.19, 1.2, mats.bedSheet, 0, 0.45, 0.35));
            bed.add(createBox(0.7, 0.1, 0.4, mats.bedMattress, 0, 0.58, -0.65));
            bed.position.set(x, 0, z);
            bed.rotation.y = rot;
            return bed;
        }}

        // Xe cứu thương
        function createAmbulance(x, z, rot=0) {{
            const amb = new THREE.Group();
            amb.add(createBox(2.0, 1.2, 3.6, mats.ambulanceWhite, 0, 0.85, 0));
            amb.add(createBox(2.04, 0.28, 3.4, mats.ambulanceRed, 0, 0.8, 0));
            amb.add(createBox(1.8, 0.5, 0.8, mats.glassWindow, 0, 1.15, 1.4));
            amb.add(createBox(0.35, 0.18, 0.7, mats.ambulanceRed, 0, 1.54, 0.2));
            const wheelMat = new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }});
            amb.add(createBox(0.25, 0.5, 0.5, wheelMat, -1.05, 0.25, 1.1));
            amb.add(createBox(0.25, 0.5, 0.5, wheelMat, 1.05, 0.25, 1.1));
            amb.add(createBox(0.25, 0.5, 0.5, wheelMat, -1.05, 0.25, -1.1));
            amb.add(createBox(0.25, 0.5, 0.5, wheelMat, 1.05, 0.25, -1.1));
            amb.position.set(x, 0, z);
            amb.rotation.y = rot;
            return amb;
        }}

        // Bàn bác sĩ
        function createDoctorDesk(x, z, rot=0) {{
            const desk = new THREE.Group();
            desk.add(createBox(1.8, 0.1, 1.0, mats.deskWood, 0, 0.7, 0));
            desk.add(createBox(0.08, 0.65, 0.9, mats.metalChrome, -0.8, 0.35, 0));
            desk.add(createBox(0.08, 0.65, 0.9, mats.metalChrome, 0.8, 0.35, 0));
            desk.add(createBox(0.7, 0.45, 0.06, mats.pcBlack, 0, 1.0, -0.15));
            desk.add(createBox(0.6, 0.7, 0.6, mats.chairBlue, 0, 0.4, -0.8));
            desk.add(createBox(0.5, 0.6, 0.5, mats.chairBlue, 0, 0.35, 0.8));
            desk.position.set(x, 0, z);
            desk.rotation.y = rot;
            return desk;
        }}

        // Quầy thuốc
        function createPharmacyCounter(x, z) {{
            const p = new THREE.Group();
            p.add(createBox(3.2, 0.85, 0.7, mats.canopyTeal, 0, 0.42, 0));
            p.add(createBox(0.7, 0.85, 1.8, mats.canopyTeal, 1.25, 0.42, 0.9));
            p.add(createBox(3.8, 1.6, 0.4, mats.shelfWood, 0, 0.8, -1.4));
            const medColors = [0xef4444, 0x10b981, 0x3b82f6, 0xf59e0b, 0x8b5cf6];
            for (let i = -1.4; i <= 1.4; i += 0.35) {{
                const mMat = new THREE.MeshStandardMaterial({{ color: medColors[Math.floor(Math.random()*medColors.length)] }});
                p.add(createBox(0.24, 0.18, 0.28, mMat, i, 1.1, -1.3));
                p.add(createBox(0.24, 0.18, 0.28, mMat, i, 0.7, -1.3));
            }}
            p.position.set(x, 0, z);
            return p;
        }}

        // Bàn mổ phẫu thuật
        function createSurgerySuite(x, z) {{
            const s = new THREE.Group();
            s.add(createBox(1.1, 0.75, 2.4, mats.metalChrome, 0, 0.4, 0));
            const lampArm = createBox(0.06, 1.0, 0.06, mats.metalChrome, 0, 1.6, 0);
            s.add(lampArm);
            const lampHead = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.12, 16), mats.canopyTeal);
            lampHead.position.set(0, 1.9, 0);
            s.add(lampHead);
            s.add(createBox(0.7, 1.3, 0.5, mats.pcBlack, -1.2, 0.65, -0.5));
            s.position.set(x, 0, z);
            return s;
        }}

        // Chậu cây
        function createPlant(x, z) {{
            const pot = new THREE.Group();
            const potMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.25, 0.6, 12), mats.potBrown);
            potMesh.position.y = 0.3;
            pot.add(potMesh);
            const foliage = new THREE.Mesh(new THREE.SphereGeometry(0.48, 12, 12), mats.plantGreen);
            foliage.position.y = 0.8;
            pot.add(foliage);
            pot.position.set(x, 0, z);
            return pot;
        }}

        // DỰNG ĐƯỜNG DẪN WAYFINDING DẠNG RIBBON BẢNG RỘNG (CỰC KỲ DỄ THẤY ĐƯỜNG ĐI)
        function createWayfindingRibbon() {{
            const group = new THREE.Group();

            // Đoạn 1: Từ ngoài sân vào sảnh chính
            group.add(createRibbonPathSegment(-4.5, 14.5, -4.5, 11.0, 0.4));
            group.add(createWaypointNode(-4.5, 14.5, 0.48, true));

            // Đoạn 2: Từ cửa sảnh vào giao lộ trước Khoa Khám bệnh
            group.add(createRibbonPathSegment(-4.5, 11.0, -4.5, 6.0, 0.4));
            group.add(createWaypointNode(-4.5, 6.0, 0.44));

            // Đoạn 3: Rẽ ngang hành lang trung tâm
            group.add(createRibbonPathSegment(-4.5, 6.0, 2.5, 6.0, 0.4));
            group.add(createWaypointNode(2.5, 6.0, 0.44));

            // Đoạn 4: Đi dọc hành lang bên phải Khoa Khám bệnh
            group.add(createRibbonPathSegment(2.5, 6.0, 2.5, 1.5, 0.4));
            group.add(createWaypointNode(2.5, 1.5, 0.44));

            // Đoạn 5: Rẽ vào Phòng khám & Xét nghiệm
            group.add(createRibbonPathSegment(2.5, 1.5, 6.5, 1.5, 0.4));
            group.add(createWaypointNode(6.5, 1.5, 0.44));

            return group;
        }}

        // ==========================================
        // DỰNG KIẾN TRÚC MẶT BẰNG TỪNG TẦNG
        // ==========================================
        function buildFloor(floorNum) {{
            if (activeFloorGroup) scene.remove(activeFloorGroup);
            labelsContainer.innerHTML = '';
            activeTags = [];

            activeFloorGroup = new THREE.Group();

            // 1. Khối đế sa bàn kiến trúc (Podium Slab màu ngọc nhạt tạo độ tương phản với nền)
            const basePodium = createBox(32.5, 0.6, 25.5, mats.podiumSlab, 0, -0.3, 0);
            activeFloorGroup.add(basePodium);

            // 2. MẶT SÀN HÀNH LANG (Màu trắng tinh khôi #ffffff nổi bật trên khối đế)
            const corridorSlab = createBox(31.2, 0.62, 24.2, mats.corridorFloor, 0, -0.29, 0);
            activeFloorGroup.add(corridorSlab);

            // 3. TƯỜNG BAO KIẾN TRÚC ISOMETRIC CÓ ĐỘ DÀY (Tường sau cao 1.6, tường trước cắt thấp 0.7)
            const wallH = 1.6;
            const wallThick = 0.45;
            activeFloorGroup.add(createWall(32, wallH, wallThick, 0, wallH/2, -12.5, false));
            activeFloorGroup.add(createWall(wallThick, wallH, 25, -16, wallH/2, 0, false));
            activeFloorGroup.add(createWall(wallThick, 0.7, 25, 16, 0.35, 0, false));
            activeFloorGroup.add(createWall(11, 0.7, wallThick, -10.5, 0.35, 12.5, false));
            activeFloorGroup.add(createWall(16, 0.7, wallThick, 8, 0.35, 12.5, false));

            // Cửa sổ kính ngoài mặt tiền
            for (let z = -9; z <= 9; z += 4.5) {{
                activeFloorGroup.add(createBox(0.48, 0.55, 1.6, mats.glassWindow, 16, 0.35, z));
            }}
            for (let x = 2; x <= 14; x += 4) {{
                activeFloorGroup.add(createBox(1.6, 0.55, 0.48, mats.glassWindow, x, 0.35, 12.5));
            }}

            // Sảnh chính đón khách (Canopy cắt thấp vừa vặn, không che khuất phòng bên trong)
            const canopy = createBox(4.5, 0.15, 1.8, mats.canopyTeal, -4.5, 1.35, 13.5);
            activeFloorGroup.add(canopy);
            activeFloorGroup.add(createBox(0.16, 1.35, 0.16, mats.metalChrome, -6.5, 0.68, 14.2));
            activeFloorGroup.add(createBox(0.16, 1.35, 0.16, mats.metalChrome, -2.5, 0.68, 14.2));
            activeFloorGroup.add(createPlant(-6.8, 13.5));
            activeFloorGroup.add(createPlant(-2.2, 13.5));

            // ==========================================
            // TẦNG 1: TIẾP ĐÓN, CẤP CỨU & KHÁM BAN ĐẦU
            // ==========================================
            if (floorNum === 1) {{
                // 1. Khoa Cấp Cứu 24/7 (ICU) - P.101 (Sàn hồng đỏ, tường ngăn rõ rệt)
                activeFloorGroup.add(createBox(10.5, 0.05, 13, mats.floorEmergency, -10.75, 0.02, 5.5));
                activeFloorGroup.add(createWall(10.5, 1.3, 0.35, -10.75, 0.65, -1.0));
                activeFloorGroup.add(createWall(0.35, 1.3, 13, -5.5, 0.65, 5.5));
                activeFloorGroup.add(createAmbulance(-11.5, 8.5, Math.PI / 4));
                activeFloorGroup.add(createHospitalBed(-10.0, 1.5, Math.PI / 2));
                activeFloorGroup.add(createHospitalBed(-13.0, 1.5, Math.PI / 2));

                // 2. Khoa Khám Bệnh & Sàng Lọc (Khối trung tâm - Sàn mint tươi)
                activeFloorGroup.add(createBox(9.0, 0.05, 8.5, mats.floorClinic, -0.5, 0.02, 0));
                activeFloorGroup.add(createWall(9.0, 1.1, 0.3, -0.5, 0.55, -4.25));
                activeFloorGroup.add(createWall(9.0, 1.1, 0.3, -0.5, 0.55, 4.25));
                activeFloorGroup.add(createWall(0.3, 1.1, 8.5, -5.0, 0.55, 0));
                activeFloorGroup.add(createWall(0.3, 1.1, 8.5, 4.0, 0.55, 0));
                activeFloorGroup.add(createWall(8.6, 0.95, 0.22, -0.5, 0.48, 0));
                activeFloorGroup.add(createWall(0.22, 0.95, 8.2, -0.5, 0.48, 0));
                activeFloorGroup.add(createDoctorDesk(-2.5, -2.0, 0));
                activeFloorGroup.add(createDoctorDesk(1.8, -2.0, 0));
                activeFloorGroup.add(createDoctorDesk(-2.5, 2.0, Math.PI));
                activeFloorGroup.add(createHospitalBed(1.8, 2.0, 0));

                // 3. Khoa Nội Tổng Quát (P.301 Quầy tiếp đón - Sàn xanh dương)
                activeFloorGroup.add(createBox(10.5, 0.05, 6.0, mats.floorInternal, 1.0, 0.02, -8.5));
                activeFloorGroup.add(createWall(10.5, 1.2, 0.3, 1.0, 0.6, -5.5));
                activeFloorGroup.add(createWall(0.3, 1.2, 6.0, -4.25, 0.6, -8.5));
                activeFloorGroup.add(createWall(0.3, 1.2, 6.0, 6.25, 0.6, -8.5));
                activeFloorGroup.add(createHospitalBed(-2.2, -8.5, 0));
                activeFloorGroup.add(createHospitalBed(1.0, -8.5, 0));
                activeFloorGroup.add(createHospitalBed(4.2, -8.5, 0));

                // 4. Khoa Ngoại (Sàn xám vô trùng)
                activeFloorGroup.add(createBox(9.0, 0.05, 8.0, mats.floorSurgery, 11.2, 0.02, -7.5));
                activeFloorGroup.add(createWall(0.3, 1.2, 8.0, 6.7, 0.6, -7.5));
                activeFloorGroup.add(createWall(9.0, 1.2, 0.3, 11.2, 0.6, -3.5));
                activeFloorGroup.add(createSurgerySuite(11.2, -7.5));

                // 5. Xét Nghiệm & Lấy Máu (P.201 Tiếp nhận - Sàn tím lavender)
                activeFloorGroup.add(createBox(9.0, 0.05, 6.5, mats.floorLab, 11.2, 0.02, 0.5));
                activeFloorGroup.add(createWall(0.3, 1.2, 6.5, 6.7, 0.6, 0.5));
                activeFloorGroup.add(createWall(9.0, 1.2, 0.3, 11.2, 0.6, 4.0));
                activeFloorGroup.add(createDoctorDesk(11.2, 0.5, Math.PI / 2));

                // 6. Nhà Thuốc Bệnh Viện (Sàn xanh ngọc tươi)
                activeFloorGroup.add(createBox(9.0, 0.05, 7.5, mats.floorPharmacy, 11.2, 0.02, 8.2));
                activeFloorGroup.add(createWall(0.3, 1.2, 7.5, 6.7, 0.6, 8.2));
                activeFloorGroup.add(createPharmacyCounter(11.2, 8.2));

                // 7. LỘ TRÌNH WAYFINDING 3D RIBBON RÕ RÀNG TRÊN HÀNH LANG
                activeFloorGroup.add(createWayfindingRibbon());

                // GẮN NHÃN GỌN GÀNG - KHÔNG CHE CHẮN
                addRoomTag("Khoa Cấp cứu (P.101)", "tag-emergency", -10.5, 1.3, 3.2, "cấp cứu");
                addRoomTag("Khoa Khám bệnh", "tag-primary-blue", -0.5, 1.3, -0.5, "khám bệnh");
                addRoomTag("Khoa Nội (P.301)", "tag-dark-blue", 1.0, 1.3, -8.5, "nội");
                addRoomTag("Khoa Ngoại", "tag-dark-blue", 11.2, 1.3, -7.5, "ngoại");
                addRoomTag("Xét nghiệm (P.201)", "tag-lab", 11.2, 1.3, 0.5, "xét nghiệm");
                addRoomTag("Nhà thuốc ATus", "tag-pharmacy", 11.2, 1.3, 8.2, "nhà thuốc");

                // Icon tiện ích nhỏ gọn
                addIconTag("🚻", "icon-restroom", -3.2, 1.0, 7.2);
                addIconTag("🚻", "icon-restroom", -0.5, 1.0, -5.2);
                addIconTag("🚻", "icon-restroom", 3.2, 1.0, 4.5);
                addIconTag("🛗", "icon-elevator", -7.5, 1.0, -5.5);
                addIconTag("❤️", "icon-heart", -7.5, 1.0, 1.5);
                addFloorText("Phòng khám Nội số 3", -4.5, 0.1, 4.2);
            }}

            // ==========================================
            // TẦNG 2: CẬN LÂM SÀNG
            // ==========================================
            else if (floorNum === 2) {{
                activeFloorGroup.add(createBox(13, 0.05, 11, mats.floorLab, -7.5, 0.02, -5.5));
                activeFloorGroup.add(createWall(13, 1.2, 0.3, -7.5, 0.6, 0));
                activeFloorGroup.add(createWall(0.3, 1.2, 11, -1.0, 0.6, -5.5));
                const mriBase = createBox(3.5, 1.8, 3.0, mats.metalChrome, -7.5, 0.9, -5.5);
                activeFloorGroup.add(mriBase);
                const mriTunnel = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.0, 3.6, 20), mats.innerWall);
                mriTunnel.rotation.z = Math.PI / 2;
                mriTunnel.position.set(-7.5, 0.9, -5.5);
                activeFloorGroup.add(mriTunnel);
                addRoomTag("P.204 - Chụp MRI 3T & CT Scanner", "tag-dark-blue", -7.5, 1.3, -5.5, "mri");

                activeFloorGroup.add(createBox(13, 0.05, 10, mats.floorSurgery, -7.5, 0.02, 5.5));
                activeFloorGroup.add(createWall(0.3, 1.2, 10, -1.0, 0.6, 5.5));
                activeFloorGroup.add(createBox(0.8, 2.0, 0.8, mats.metalChrome, -7.5, 1.0, 5.5));
                addRoomTag("P.203 - Chụp X-Quang Kỹ Thuật Số", "tag-dark-blue", -7.5, 1.3, 5.5, "xquang");

                activeFloorGroup.add(createBox(13, 0.05, 11, mats.floorLab, 7.5, 0.02, -5.5));
                activeFloorGroup.add(createWall(13, 1.2, 0.3, 7.5, 0.6, 0));
                activeFloorGroup.add(createWall(0.3, 1.2, 11, 1.0, 0.6, -5.5));
                activeFloorGroup.add(createDoctorDesk(7.5, -5.5, 0));
                addRoomTag("P.201 - Lấy Máu & Xét Nghiệm", "tag-lab", 7.5, 1.3, -5.5, "máu");

                activeFloorGroup.add(createBox(13, 0.05, 10, mats.floorClinic, 7.5, 0.02, 5.5));
                activeFloorGroup.add(createWall(0.3, 1.2, 10, 1.0, 0.6, 5.5));
                activeFloorGroup.add(createDoctorDesk(7.5, 5.5, 0));
                addRoomTag("P.202 - Đo Chức Năng Hô Hấp", "tag-pharmacy", 7.5, 1.3, 5.5, "hô hấp");

                addIconTag("🛗", "icon-elevator", 0, 1.0, -10.5);
                addIconTag("🚻", "icon-restroom", 0, 1.0, 10.5);
            }}

            // ==========================================
            // TẦNG 3: KHÁM CHUYÊN KHOA
            // ==========================================
            else if (floorNum === 3) {{
                activeFloorGroup.add(createBox(8.5, 0.05, 9, mats.floorInternal, -9.5, 0.02, -5.5));
                activeFloorGroup.add(createWall(8.5, 1.1, 0.25, -9.5, 0.55, -1.0));
                activeFloorGroup.add(createDoctorDesk(-9.5, -5.5, 0));
                addRoomTag("P.301 - Khám Nội Tổng Quát", "tag-primary-blue", -9.5, 1.3, -5.5, "nội");

                activeFloorGroup.add(createBox(8.5, 0.05, 9, mats.floorClinic, 0, 0.02, -5.5));
                activeFloorGroup.add(createWall(8.5, 1.1, 0.25, 0, 0.55, -1.0));
                activeFloorGroup.add(createWall(0.25, 1.1, 9, -5.25, 0.55, -5.5));
                activeFloorGroup.add(createWall(0.25, 1.1, 9, 4.25, 0.55, -5.5));
                activeFloorGroup.add(createDoctorDesk(0, -5.5, 0));
                activeFloorGroup.add(createBox(0.8, 1.2, 0.05, mats.deskWood, 0, 1.2, -9.8));
                addRoomTag("P.302 - Chuyên Khoa Mắt", "tag-primary-blue", 0, 1.3, -5.5, "mắt");

                activeFloorGroup.add(createBox(8.5, 0.05, 9, mats.floorClinic, 9.5, 0.02, -5.5));
                activeFloorGroup.add(createWall(8.5, 1.1, 0.25, 9.5, 0.55, -1.0));
                activeFloorGroup.add(createDoctorDesk(9.5, -5.5, 0));
                addRoomTag("P.303 - Tai Mũi Họng", "tag-dark-blue", 9.5, 1.3, -5.5, "tai mũi họng");

                activeFloorGroup.add(createBox(11, 0.05, 8.5, mats.floorClinic, -6, 0.02, 6.0));
                activeFloorGroup.add(createWall(11, 1.1, 0.25, -6, 0.55, 1.75));
                activeFloorGroup.add(createWall(0.25, 1.1, 8.5, -0.5, 0.55, 6.0));
                activeFloorGroup.add(createHospitalBed(-6, 6.0, Math.PI / 4));
                addRoomTag("P.304 - Răng Hàm Mặt", "tag-pharmacy", -6, 1.3, 6.0, "răng");

                activeFloorGroup.add(createBox(11, 0.05, 8.5, mats.floorClinic, 6, 0.02, 6.0));
                activeFloorGroup.add(createWall(11, 1.1, 0.25, 6, 0.55, 1.75));
                activeFloorGroup.add(createDoctorDesk(6, 6.0, Math.PI));
                addRoomTag("P.305 - Da Liễu", "tag-pharmacy", 6, 1.3, 6.0, "da liễu");

                addIconTag("🛗", "icon-elevator", 0, 1.0, -10.5);
                addIconTag("🚻", "icon-restroom", -0.5, 1.0, 10.5);
            }}

            // ==========================================
            // TẦNG 4: SẢN & NHI
            // ==========================================
            else if (floorNum === 4) {{
                activeFloorGroup.add(createBox(13, 0.05, 18, mats.floorInternal, -7.5, 0.02, 0));
                activeFloorGroup.add(createWall(0.3, 1.2, 18, -1.0, 0.6, 0));
                activeFloorGroup.add(createHospitalBed(-7.5, -4, 0));
                activeFloorGroup.add(createDoctorDesk(-7.5, 4, 0));
                addRoomTag("P.401 - Khám Sản Phụ Khoa", "tag-primary-blue", -7.5, 1.3, 0, "sản");

                activeFloorGroup.add(createBox(13, 0.05, 18, mats.floorClinic, 7.5, 0.02, 0));
                activeFloorGroup.add(createWall(0.3, 1.2, 18, 1.0, 0.6, 0));
                activeFloorGroup.add(createDoctorDesk(7.5, -4, 0));
                activeFloorGroup.add(createHospitalBed(7.5, 4, 0));
                addRoomTag("P.402 - Khám Nhi & Tiêm Chủng", "tag-pharmacy", 7.5, 1.3, 0, "nhi");

                addIconTag("🛗", "icon-elevator", 0, 1.0, -10.5);
                addIconTag("🚻", "icon-restroom", 0, 1.0, 10.5);
            }}

            scene.add(activeFloorGroup);
        }}

        // Gắn nhãn phòng HTML
        function addRoomTag(text, tagClass, x, y, z, key) {{
            const div = document.createElement('div');
            div.className = `room-tag ${{tagClass}}`;
            div.innerText = text;
            labelsContainer.appendChild(div);

            const isTarget = TARGET_DEPT && (
                key.toLowerCase().includes(TARGET_DEPT.toLowerCase()) ||
                text.toLowerCase().includes(TARGET_DEPT.toLowerCase()) ||
                TARGET_DEPT.toLowerCase().includes(key.toLowerCase())
            );

            if (isTarget) {{
                div.classList.add('tag-highlight');
            }}

            activeTags.push({{
                el: div,
                pos: new THREE.Vector3(x, y, z)
            }});
        }}

        // Gắn icon tiện ích
        function addIconTag(emoji, iconClass, x, y, z) {{
            const div = document.createElement('div');
            div.className = `icon-tag ${{iconClass}}`;
            div.innerText = emoji;
            labelsContainer.appendChild(div);
            activeTags.push({{
                el: div,
                pos: new THREE.Vector3(x, y, z)
            }});
        }}

        // Nhãn văn bản dán sàn
        function addFloorText(text, x, y, z) {{
            const div = document.createElement('div');
            div.className = 'floor-text-label';
            div.innerText = text;
            labelsContainer.appendChild(div);
            activeTags.push({{
                el: div,
                pos: new THREE.Vector3(x, y, z)
            }});
        }}

        // Chuyển tầng
        function switchFloor(floorNum) {{
            [1, 2, 3, 4].forEach(f => {{
                const btn = document.getElementById(`fbtn-${{f}}`);
                if (btn) btn.classList.toggle('active', f === floorNum);
            }});
            buildFloor(floorNum);
        }}

        // Nút Đặt Lịch Khám
        function triggerBooking() {{
            window.parent.postMessage({{ type: 'STREAMLIT_SET_MENU', menu: 'Đặt lịch hẹn' }}, '*');
            const bookBtn = window.parent.document.querySelector('button[key="btn_go_book"]');
            if (bookBtn) bookBtn.click();
        }}

        // Zoom In / Out cho OrthographicCamera
        function zoomIn() {{
            camera.zoom = Math.min(camera.zoom * 1.25, 2.5);
            camera.updateProjectionMatrix();
        }}
        function zoomOut() {{
            camera.zoom = Math.max(camera.zoom / 1.25, 0.7);
            camera.updateProjectionMatrix();
        }}

        // Khởi tạo ban đầu
        const initFloor = [1, 2, 3, 4].includes(TARGET_FLOOR) ? TARGET_FLOOR : 1;
        switchFloor(initFloor);

        // Render loop
        function animate() {{
            requestAnimationFrame(animate);
            controls.update();

            activeTags.forEach(t => {{
                const p = t.pos.clone().project(camera);
                const x = (p.x * 0.5 + 0.5) * container.clientWidth;
                const y = (-p.y * 0.5 + 0.5) * container.clientHeight;
                t.el.style.left = `${{x}}px`;
                t.el.style.top = `${{y}}px`;
                t.el.style.display = (p.z > 1) ? 'none' : 'block';
            }});

            renderer.render(scene, camera);
        }}
        animate();

        // Responsive khi resize
        window.addEventListener('resize', () => {{
            const newAspect = container.clientWidth / container.clientHeight;
            camera.left = -frustumSize * newAspect / 2;
            camera.right = frustumSize * newAspect / 2;
            camera.top = frustumSize / 2;
            camera.bottom = -frustumSize / 2;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }});
    </script>
</body>
</html>
"""
