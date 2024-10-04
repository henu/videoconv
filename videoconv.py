#!/usr/bin/env python3
import argparse
import asyncio
import magic
import os
import random
import string
import sys
import tempfile


PROBLEMATIC_FILES = (
    'Microsoft ASF',
)


async def main():
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

    # If input files do not exist, then raise an error
    for input_path in input_paths:
        if not os.path.exists(input_path):
            raise RuntimeError(f'Input file {input_path} does not exist!')

    # If there is only one file, then just convert it
    if len(input_paths) == 1:
        await convert_video(input_paths[0], output_path)

    # If there are multiple files
    else:

        # If even one of the files is problematic, then first convert them into temporary videos
        problematic_found = False
        for input_path in input_paths:
            if is_problematic(input_path):
                problematic_found = True
                break
        if problematic_found:
            # Convert
            conversion_tasks = []
            for input_path in input_paths:
                conversion_tasks.append(convert_to_temporary_video(input_path))
            temporary_paths = await asyncio.gather(*conversion_tasks)
            # Merge
            await merge_videos(temporary_paths, output_path)
            # Clean
            for temporary_path in temporary_paths:
                os.remove(temporary_path)

        # No problematic files were found, so just merge them
        else:
            await merge_videos(input_paths, output_path)


def is_problematic(path):
    return magic.from_file(path) in PROBLEMATIC_FILES


def get_temp_filename():
    filename = 'tmp' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '.mp4'
    return os.path.join(tempfile.gettempdir(), filename)


async def run_command(*args):
    command = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        stdin=asyncio.subprocess.PIPE,
    )
    await command.communicate()


async def convert_video(input_path, output_path):
    await run_command(
        'ffmpeg',
        '-loglevel', 'quiet',
        '-i', input_path,
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
    )


async def merge_videos(input_paths, output_path):
    with tempfile.TemporaryDirectory() as tmp_path:
        # Construct videolist
        videolist_path = os.path.join(tmp_path, 'videolist')
        with open(videolist_path, 'w') as videolist_file:
            for input_path in input_paths:
                input_path_abs = os.path.abspath(input_path)
                videolist_file.write(f'file \'{input_path_abs}\'\n')
        await run_command(
            'ffmpeg',
            '-loglevel', 'quiet',
            '-f', 'concat', '-safe', '0', '-i', videolist_path,
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
        )


async def convert_to_temporary_video(path):
    temp_path = get_temp_filename()
    await convert_video(path, temp_path)
    return temp_path


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError as err:
        print(f'Error: {err}')
        sys.exit(1)
