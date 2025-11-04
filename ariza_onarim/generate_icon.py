#!/usr/bin/env python3
"""
Basit PNG ikon oluşturma - SVG'den PNG'ye dönüştürme alternatifi
"""

import subprocess
import sys
import os

def try_convert_with_inkscape():
    """Inkscape ile SVG'den PNG'ye dönüştür"""
    svg_path = "static/description/icon.svg"
    png_path = "static/description/icon.png"
    
    if os.path.exists(svg_path):
        try:
            result = subprocess.run(
                ['inkscape', '--export-type=png', '--export-width=128', '--export-height=128', 
                 f'--export-filename={png_path}', svg_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ Inkscape ile PNG oluşturuldu: {png_path}")
                return True
        except FileNotFoundError:
            pass
    return False

def try_convert_with_rsvg():
    """rsvg-convert ile SVG'den PNG'ye dönüştür"""
    svg_path = "static/description/icon.svg"
    png_path = "static/description/icon.png"
    
    if os.path.exists(svg_path):
        try:
            result = subprocess.run(
                ['rsvg-convert', '-w', '128', '-h', '128', '-o', png_path, svg_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ rsvg-convert ile PNG oluşturuldu: {png_path}")
                return True
        except FileNotFoundError:
            pass
    return False

def create_simple_png_with_pillow():
    """Pillow ile basit PNG oluştur (eğer kuruluysa)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import os
        
        size = (128, 128)
        img = Image.new('RGB', size, color='#667EEA')
        draw = ImageDraw.Draw(img)
        
        # Gradient arka plan (basit)
        for i in range(size[1]):
            ratio = i / size[1]
            r = int(102 + (118 - 102) * ratio)
            g = int(126 + (75 - 126) * ratio)
            b = int(234 + (162 - 234) * ratio)
            draw.line([(0, i), (size[0], i)], fill=(r, g, b))
        
        # Yuvarlatılmış köşeler için mask
        mask = Image.new('L', size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), size], radius=24, fill=255)
        
        # Ana çekiç şekli
        # Çekiç başı
        draw.ellipse([30, 20, 65, 55], fill='white', outline='#4A5568', width=3)
        draw.ellipse([35, 25, 60, 50], fill='#F0F0F0')
        
        # Çekiç sapı
        draw.rounded_rectangle([20, 35, 75, 45], radius=8, fill='white', outline='#4A5568', width=3)
        draw.line([30, 35, 30, 45], fill='#4A5568', width=1)
        draw.line([40, 35, 40, 45], fill='#4A5568', width=1)
        
        # Tornavida
        draw.rounded_rectangle([75, 20, 85, 95], radius=5, fill='white', outline='#4A5568', width=3)
        draw.rounded_rectangle([73, 15, 87, 25], radius=3, fill='#FFD700', outline='#4A5568', width=2)
        draw.rectangle([78, 95, 82, 105], fill='#4A5568')
        
        # Merkez dişli
        center_x, center_y = 64, 64
        draw.ellipse([center_x-15, center_y-15, center_x+15, center_y+15], outline='#FFD700', width=3)
        draw.ellipse([center_x-10, center_y-10, center_x+10, center_y+10], outline='#FFD700', width=2)
        draw.ellipse([center_x-5, center_y-5, center_x+5, center_y+5], fill='#FFD700')
        
        # Mask uygula
        img.putalpha(mask)
        
        # PNG olarak kaydet
        output_path = 'static/description/icon.png'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, 'PNG')
        print(f"✅ Pillow ile PNG oluşturuldu: {output_path}")
        return True
        
    except ImportError:
        return False

if __name__ == "__main__":
    print("🔄 PNG ikon oluşturuluyor...")
    
    # Önce Pillow ile dene
    if create_simple_png_with_pillow():
        sys.exit(0)
    
    # Inkscape ile dene
    if try_convert_with_inkscape():
        sys.exit(0)
    
    # rsvg-convert ile dene
    if try_convert_with_rsvg():
        sys.exit(0)
    
    print("⚠️  PNG oluşturulamadı. Şu yöntemlerden birini deneyin:")
    print("   1. pip install Pillow")
    print("   2. Inkscape kur (macOS: brew install inkscape)")
    print("   3. rsvg-convert kur (macOS: brew install librsvg)")
    print("   4. Online SVG to PNG converter kullanın")

