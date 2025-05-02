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


DEFAULT_CRF = 23


async def main():
    # Read arguments
    parser = argparse.ArgumentParser(
        description='Convert one or more files into a single video.',
    )
    parser.add_argument('input_file', type=str, nargs='*', help='One or more input files')
    parser.add_argument('output_file', type=str, nargs=1, help='Output file, or input and output file, if they are the same file.')
    parser.add_argument('--max-size', type=int, help='Maximum limit for output file in mebibytes.')
    args = parser.parse_args()
    input_paths = args.input_file
    output_path = args.output_file[0]
    max_size = args.max_size * 1024 * 1024 if args.max_size else None

    # If input files do not exist, then raise an error
    for input_path in input_paths:
        if not os.path.exists(input_path):
            raise RuntimeError(f'Input file {input_path} does not exist!')

    # If output file already exists, then raise an error
    if input_paths and os.path.exists(output_path):
        raise RuntimeError('Output file already exists!')

    # If there is only one file, then just convert it
    if len(input_paths) == 1:
        await convert_video(input_paths[0], output_path, max_size=max_size)

    # If there is no input files, then convert the existing file and use the same name as output
    elif not input_paths:
        if not os.path.exists(output_path):
            raise RuntimeError(f'Input file {output_path} does not exist!')
        temp_file_path = get_temp_filename(filename_prefix=output_path, temp_dir='')
        await convert_video(output_path, temp_file_path, max_size=max_size)
        os.replace(temp_file_path, output_path)

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
            await merge_videos(temporary_paths, output_path, max_size=max_size)
            # Clean
            for temporary_path in temporary_paths:
                os.remove(temporary_path)

        # No problematic files were found, so just merge them
        else:
            await merge_videos(input_paths, output_path, max_size=max_size)


def is_problematic(path):
    #return magic.from_file(path) in PROBLEMATIC_FILES
    # For now, consider all formats problematic
    return True


def get_temp_filename(filename_prefix='tmp', temp_dir=None):
    # TODO: Make sure file does not exist!
    filename = filename_prefix + ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '.mp4'
    if temp_dir is not None:
        return os.path.join(temp_dir, filename)
    return os.path.join(tempfile.gettempdir(), filename)


async def run_command(*args):
    command = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        stdin=asyncio.subprocess.PIPE,
    )
    await command.communicate()


class ByterateDecider:

    def __init__(self, max_size):
        # Options
        self.max_size = max_size
        # Analysis
        self.last_crf = None
        self.analysis = {}

    def check_output_file(self, output_path):
        # If file does not exist yet, then it means should always start encoding
        if not os.path.exists(output_path):
            return True

        # If file exists, and maximum size is not set, then simply consider everything ready
        if not self.max_size:
            return False

        # Get file size
        file_size = os.path.getsize(output_path)

        # Store the analysis result
        assert self.last_crf
        self.analysis[self.last_crf] = file_size

        # If the file is small enough with default CRF, then stop
        if file_size <= self.max_size and self.last_crf == DEFAULT_CRF:
            return False

        # If the perfect CRF has been found, then stop
        if file_size == self.max_size:
            return False
        if file_size <= self.max_size:
            better_crf_file_size = self.analysis.get(self.last_crf - 1)
            if better_crf_file_size is not None and better_crf_file_size > self.max_size:
                return False

        # In other cases, keep trying
        os.remove(output_path)
        return True

    def get_crf(self):
        # If maximum size is not set, then use default
        if not self.max_size:
            return DEFAULT_CRF

        # If there are no analysis done, then use default
        if not self.analysis:
            self.last_crf = DEFAULT_CRF
            return self.last_crf

        # If the last try resulted to too big video
        if self.analysis[self.last_crf] > self.max_size:
            # Check if bigger CRF has already been tried
            bigger_crfs = sorted(crf for crf in self.analysis.keys() if crf > self.last_crf)
            if bigger_crfs:
                bigger_crf = bigger_crfs[0]
                assert self.analysis[bigger_crf] < self.max_size
                # If the bigger CRF was actually the perfect value, then return it
                if bigger_crf == self.last_crf + 1:
                    self.last_crf = bigger_crf
                    return self.last_crf
                # A new CRF is a value between the last and the bigger CRF
                self.last_crf = (self.last_crf + bigger_crf) // 2
                return self.last_crf
            # If there was no bigger CRF, then try to double it
            self.last_crf *= 2
            return self.last_crf

        # The last try resulted to too small video
        smaller_crfs = sorted(crf for crf in self.analysis.keys() if crf < self.last_crf)
        assert smaller_crfs
        smaller_crf = smaller_crfs[-1]
        assert self.analysis[smaller_crf] > self.max_size
        assert self.last_crf - smaller_crf >= 2
        # A new CRF is a value between the last and the smaller CRF
        self.last_crf = (self.last_crf + smaller_crf) // 2
        return self.last_crf


async def convert_video(input_path, output_path, max_size=None):

    byterate_decider = ByterateDecider(max_size=max_size)

    while byterate_decider.check_output_file(output_path):

        await run_command(
            'ffmpeg',
            '-loglevel', 'quiet',
            '-i', input_path,
            '-c:v', 'libx264',
            '-crf', str(byterate_decider.get_crf()),
            '-profile:v',
            'baseline',
            '-level', '3.0',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-ac', '2',
            '-b:a', '128k',
            '-movflags',
            'faststart',
            '-map_metadata', '-1',
            output_path,
        )


async def merge_videos(input_paths, output_path, max_size=None):

    byterate_decider = ByterateDecider(max_size=max_size)

    while byterate_decider.check_output_file(output_path):

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
                '-crf', str(byterate_decider.get_crf()),
                '-profile:v',
                'baseline',
                '-level', '3.0',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-ac', '2',
                '-b:a', '128k',
                '-movflags',
                'faststart',
                '-map_metadata', '-1',
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
