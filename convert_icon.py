from cairosvg import svg2png
import os

# SVG dosyasının yolu
svg_path = 'ariza_onarim/static/description/icon.svg'
# PNG dosyasının yolu
png_path = 'ariza_onarim/static/description/icon.png'

# SVG'yi PNG'ye dönüştür
with open(svg_path, 'rb') as svg_file:
    svg2png(file_obj=svg_file, write_to=png_path, output_width=512, output_height=512)

print(f"İkon başarıyla oluşturuldu: {png_path}") 