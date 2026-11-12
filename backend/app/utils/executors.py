from concurrent.futures import ThreadPoolExecutor

ffmpeg_executor = ThreadPoolExecutor(max_workers=1)

io_executor = ThreadPoolExecutor(max_workers=2)
