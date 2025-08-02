#!/usr/bin/env python3
"""
SVG ikonu PNG'ye dönüştürme scripti
"""

import cairosvg
import os

def convert_svg_to_png():
    """SVG dosyasını PNG'ye dönüştürür"""
    svg_path = "static/description/icon.svg"
    png_path = "static/description/icon.png"
    
    if os.path.exists(svg_path):
        try:
            cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=140, output_height=140)
            print(f"✅ SVG başarıyla PNG'ye dönüştürüldü: {png_path}")
        except Exception as e:
            print(f"❌ Dönüştürme hatası: {e}")
    else:
        print(f"❌ SVG dosyası bulunamadı: {svg_path}")

if __name__ == "__main__":
    convert_svg_to_png() 