#!/bin/zsh
set -e
T=~/Documents/UAL/tangible-worlds  # the thesis repository; adjust to your checkout
O=public/media/video
SRC="$T/Part 2.2.mov"
# Hero desktop: tracker RGB inset (left) | production renderer (right), 1600x900
ffmpeg -v error -y -i "$SRC" -filter_complex "[0:v]crop=394:502:56:386,scale=706:900:flags=lanczos,setsar=1[p];[0:v]crop=834:840:540:110,scale=894:900:flags=lanczos,setsar=1[d];[p][d]hstack=inputs=2,fps=30,format=yuv420p[v]" -map "[v]" -an -c:v libx264 -preset slow -crf 23 -profile:v high -movflags +faststart $O/hero-split.mp4
# Hero mobile: stacked 720x1280
ffmpeg -v error -y -i "$SRC" -filter_complex "[0:v]crop=394:350:56:450,scale=720:640:flags=lanczos,setsar=1[p];[0:v]crop=834:741:540:110,scale=720:640:flags=lanczos,setsar=1[d];[p][d]vstack=inputs=2,fps=30,format=yuv420p[v]" -map "[v]" -an -c:v libx264 -preset slow -crf 24 -movflags +faststart $O/hero-split-mobile.mp4
ffmpeg -v error -y -ss 4 -i $O/hero-split.mp4 -frames:v 1 -q:v 3 public/media/img/hero-poster.jpg
ffmpeg -v error -y -ss 4 -i $O/hero-split-mobile.mp4 -frames:v 1 -q:v 3 public/media/img/hero-poster-mobile.jpg
# Unedited full-frame Part 2.2 for reference
ffmpeg -v error -y -i "$SRC" -vf "scale=1280:-2,fps=30,format=yuv420p" -an -c:v libx264 -preset slow -crf 25 -movflags +faststart $O/part-2-2-full.mp4
# Voice assignment evidence (part 1.1) and atmosphere evidence (Part 3.3)
ffmpeg -v error -y -i "$T/part 1.1.mov" -vf "scale=1280:-2,fps=30,format=yuv420p" -an -c:v libx264 -preset slow -crf 26 -movflags +faststart $O/voice-assignment.mp4
ffmpeg -v error -y -i "$T/Part 3.3.mov" -vf "scale=1280:-2,fps=30,format=yuv420p" -an -c:v libx264 -preset slow -crf 26 -movflags +faststart $O/atmosphere-voice.mp4
# Full working prototype demonstration
ffmpeg -v error -y -i "$T/Tangible-Worlds-Thesis/Tangible World Working Prototype.mov" -vf "scale=1280:-2,fps=30,format=yuv420p" -an -c:v libx264 -preset slow -crf 27 -movflags +faststart $O/working-prototype.mp4
ffmpeg -v error -y -ss 150 -i $O/working-prototype.mp4 -frames:v 1 -q:v 3 public/media/img/prototype-poster.jpg
echo DONE
ls -la $O public/media/img
