# «Увидел → Крикнул → Выиграл!» — бумажный финал

`tipo_word_sequence_v4_paper_crumple_1080p.mp4`: 1920 × 1080, 30 кадров/с, 158 кадров, 5,267 секунды, H.264 MP4, без звука.

Одобренная анимация версии 3 сохранена полностью: первые 92 исходных PNG-кадра используются без изменения. Затем весь синий кадр с надписью «ВЫИГРАЛ!» становится одним листом бумаги. Лист собирается в складки и сжимается в небольшой неровный комок. Он уходит вниз из кадра, оставляя однотонный розовый фон `#FF006F`. Последние 15 кадров гарантированно пустые.

Сминание выполнено как 3D-деформация одного связного листа с исходным изображением в UV-развёртке. Деформируются и фон, и буквы; это не масштабирование плоского кадра. Видны складки, грани, бумажная толщина и светлая оборотная сторона. 17 отдельных поз удерживаются по три кадра без временной интерполяции. Камера неподвижна.

Исходники находятся в `word_sequence_v4/`. `assets/final_word_frame.png` — последний кадр одобренной версии. `build_crumple.py` создаёт позы бумажного листа в Blender 4.3.2 (EEVEE). `assemble_animation.py` присоединяет их к исходной анимации и добавляет пустой финал. Для сборки нужны Python, Pillow и исходники `word_sequence_v3/`; если PNG-последовательности версии 3 нет, она восстанавливается её скриптом автоматически.

```bash
blender -b -t 4 -P word_sequence_v4/build_crumple.py
python word_sequence_v4/assemble_animation.py
ffmpeg -framerate 30 -i word_sequence_v4/frames/frame_%04d.png -an -vf 'scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p' -c:v libx264 -preset slow -crf 16 -color_range tv -colorspace bt709 -color_trc bt709 -color_primaries bt709 -movflags +faststart tipo_word_sequence_v4_paper_crumple_1080p.mp4
```

Параметры поз находятся в `paper_poses.json`, соответствие кадров — в `animation_manifest.json`, результаты проверки — в `video_validation.json`.
