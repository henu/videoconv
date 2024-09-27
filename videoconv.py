#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import tempfile


def main():
    # Read arguments
    parser = argparse.ArgumentParser(
        description='Convert one or more files into a single video.',
    )
    parser.add_argument('input_file', type=str, nargs='+', help='One or more input files')
    parser.add_argument('output_file', type=str, nargs=1, help='Output file')
    args = parser.parse_args()
    input_paths = args.input_file
    output_path = args.output_file[0]

    # If output file already exists, then raise an error
    if os.path.exists(output_path):
        raise RuntimeError('Output file already exists!')

    # Use temporary directory, in case there are multiple input files
    with tempfile.TemporaryDirectory() as tmp_path:

        # Start building the FFmpeg command
        ffmpeg_command = ['ffmpeg', '-loglevel', 'quiet']

        # If there are multiple files, then create a file list for them
        if len(input_paths) > 1:
            # Construct videolist
            videolist_path = os.path.join(tmp_path, 'videolist')
            with open(videolist_path, 'w') as videolist_file:
                for input_path in input_paths:
                    input_path_abs = os.path.abspath(input_path)
                    videolist_file.write(f'file \'{input_path_abs}\'\n')
            # Update the FFmpeg command
            ffmpeg_command += ['-f', 'concat', '-safe', '0', '-i', videolist_path]

        # If there is only one input file
        else:
            ffmpeg_command += ['-i', input_paths[0]]

        # Finalize the FFmpeg command
        ffmpeg_command += [
            '-c:v', 'libx264',
            '-crf', '23',
            '-profile:v',
            'baseline',
            '-level', '3.0',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-ac', '2',
            '-b:a', '128k',
            '-movflags',
            'faststart',
            output_path,
        ]

        # Run the FFmpeg command
        subprocess.run(ffmpeg_command, stdout=subprocess.PIPE)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as err:
        print(f'Error: {err}')
        sys.exit(1)
