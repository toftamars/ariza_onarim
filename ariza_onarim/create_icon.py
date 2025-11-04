#!/usr/bin/env python3
"""
Basit PNG ikon oluşturma scripti (Pillow kullanarak)
"""

try:
    from PIL import Image, ImageDraw
    import os
    
    def create_icon():
        """Basit bir PNG ikon oluşturur"""
        size = (128, 128)
        
        # Gradient arka plan oluştur
        img = Image.new('RGB', size, color='#667EEA')
        draw = ImageDraw.Draw(img)
        
        # Gradient efekti (basit)
        for i in range(size[1]):
            ratio = i / size[1]
            r = int(102 + (118 - 102) * ratio)  # 667EEA -> 764BA2
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
        
        # Merkez dişli sembolü
        center_x, center_y = 64, 64
        draw.ellipse([center_x-15, center_y-15, center_x+15, center_y+15], 
                    outline='#FFD700', width=3)
        draw.ellipse([center_x-10, center_y-10, center_x+10, center_y+10], 
                    outline='#FFD700', width=2)
        draw.ellipse([center_x-5, center_y-5, center_x+5, center_y+5], 
                    fill='#FFD700')
        
        # Dekoratif noktalar
        draw.ellipse([20, 20, 28, 28], fill='white')
        draw.ellipse([100, 100, 108, 108], fill='white')
        
        # Mask uygula (yuvarlatılmış köşeler)
        img.putalpha(mask)
        
        # PNG olarak kaydet
        output_path = 'static/description/icon.png'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, 'PNG')
        print(f"✅ PNG ikon oluşturuldu: {output_path}")
        
    if __name__ == "__main__":
        create_icon()
        
except ImportError:
    print("⚠️  Pillow (PIL) kurulu değil. SVG ikon kullanılacak.")
    print("💡 PNG ikon için: pip install Pillow")

