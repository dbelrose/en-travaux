from moviepy import ImageClip, TextClip, concatenate_videoclips, CompositeVideoClip, ColorClip

# Fichiers images
image_files = [
    "IMG_20201225_134511.jpg",
    "DSCF3528.JPG",
    "article_tennis-table_LNC_VN_07092011.jpg",
    "IMG_20190731_111049.jpg",
    "IMG_3989.JPG",
    "IMG_3764.JPG",
    "_DSC0705-1.jpg",
    "_DSC0570-3.jpg",
    "_DSC0582-4.jpg",
]

# Paramètres
duration_per_image = 8
intro_duration = 4
outro_duration = 4
video_size = (1280, 720)

# Intro
intro_bg = ColorClip(size=video_size, color=(64, 224, 208)).with_duration(intro_duration)
intro_text = TextClip(
    font="C:/Windows/Fonts/arial.ttf",
    text="Joyeux anniversaire Alize !",
    font_size=70,
    color='yellow'
).with_duration(intro_duration).with_position('center')

intro_clip = CompositeVideoClip([intro_bg, intro_text])

# Outro
outro_bg = ColorClip(size=video_size, color=(255, 127, 80)).with_duration(outro_duration)
outro_text = TextClip(
    font="C:/Windows/Fonts/arial.ttf",
    text="Alize, que le show continue !",
    font_size=60,
    color='white'
).with_duration(outro_duration).with_position('center')

outro_clip = CompositeVideoClip([outro_bg, outro_text])

# Images avec effets
image_clips = []
for idx, img in enumerate(image_files):
    clip = ImageClip(img).with_duration(duration_per_image)

    # Redimensionner en gardant le ratio
    clip = clip.resized(height=video_size[1])

    # Si l'image est plus large que la vidéo, on la recadre
    if clip.w > video_size[0]:
        clip = clip.cropped(x_center=clip.w / 2, width=video_size[0])
    else:
        # Sinon, on centre l'image sur un fond noir
        bg = ColorClip(size=video_size, color=(0, 0, 0)).with_duration(duration_per_image)
        x_pos = (video_size[0] - clip.w) // 2
        clip = clip.with_position((x_pos, 0))
        clip = CompositeVideoClip([bg, clip])

    # Effets
    if idx == 0:
        clip = clip.resized(1.05)  # Zoom léger
    # Les autres clips restent sans effet pour simplifier

    image_clips.append(clip)

# Assemblage
final_video = concatenate_videoclips([intro_clip] + image_clips + [outro_clip], method="compose")
final_video.write_videofile("joyeux_anniversaire_alize.mp4", fps=24)

print("Vidéo créée avec succès !")
