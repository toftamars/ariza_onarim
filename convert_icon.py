import cairosvg
import os

# SVG dosyasının yolu
svg_path = 'ariza_onarim/static/description/icon.svg'
# PNG dosyasının yolu
png_path = 'ariza_onarim/static/description/icon.png'

# SVG'yi PNG'ye dönüştür
cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=140, output_height=140)

print(f"İkon başarıyla oluşturuldu: {png_path}") 