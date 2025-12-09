"""
아이콘 생성 스크립트
pillow 없이 간단한 PNG 생성
"""
import struct
import zlib

def create_simple_png(size, filename):
    """간단한 그라데이션 PNG 생성"""
    width = height = size

    # 픽셀 데이터 생성 (RGBA)
    pixels = []
    for y in range(height):
        row = []
        for x in range(width):
            # 그라데이션 색상 (보라색 계열)
            t = (x + y) / (width + height)
            r = int(102 + (118 - 102) * t)  # 667eea -> 764ba2
            g = int(126 + (75 - 126) * t)
            b = int(234 + (162 - 234) * t)
            a = 255

            # 둥근 모서리
            corner_radius = size // 4
            in_corner = False

            # 각 코너 체크
            corners = [
                (corner_radius, corner_radius),
                (width - corner_radius - 1, corner_radius),
                (corner_radius, height - corner_radius - 1),
                (width - corner_radius - 1, height - corner_radius - 1)
            ]

            for cx, cy in corners:
                if (x < corner_radius or x >= width - corner_radius) and \
                   (y < corner_radius or y >= height - corner_radius):
                    dx = abs(x - cx)
                    dy = abs(y - cy)
                    if dx * dx + dy * dy > corner_radius * corner_radius:
                        a = 0
                        break

            row.extend([r, g, b, a])
        pixels.append(bytes([0] + row))  # 필터 바이트 추가

    raw_data = b''.join(pixels)

    # PNG 파일 생성
    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    # PNG 헤더
    png = b'\x89PNG\r\n\x1a\n'

    # IHDR 청크
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    png += png_chunk(b'IHDR', ihdr_data)

    # IDAT 청크 (압축된 이미지 데이터)
    compressed = zlib.compress(raw_data, 9)
    png += png_chunk(b'IDAT', compressed)

    # IEND 청크
    png += png_chunk(b'IEND', b'')

    with open(filename, 'wb') as f:
        f.write(png)

    print(f'Created: {filename}')

# 아이콘 생성
create_simple_png(16, 'icons/icon16.png')
create_simple_png(48, 'icons/icon48.png')
create_simple_png(128, 'icons/icon128.png')

print('Icons created successfully!')
