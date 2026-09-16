videoconv
=========

This tool uses FFmpeg to convert videos to format that has good quality, doesn't take too much disk space, and is
supported by most of the operating systems and applications.

The tool also focuses on simplicity. Currently there are only two types of arguments:

1. One or more input files
2. A single output file

Here is an example how to use the tool:

```
./videoconv.py input_video1.avi input_video2.avi output_video.mp4
```

The output is an MP4 file. If the output name ends in `.mkv`, a Matroska file is written instead and all audio and
subtitle tracks are kept.

If only one file is given, it is converted in place and keeps its name. A file that is not already `.mp4` or `.mkv`
becomes `.mp4` and the original is removed.

The only option is `--max-size`, which limits the output file size in mebibytes. The tool re-encodes at different
quality levels until it finds the best one that fits.
