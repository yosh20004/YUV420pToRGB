import ctypes
import os # 用于路径处理
import time # 用于性能测试

# --- 配置 ---
IMG_WIDTH = 1920  # 图像宽度
IMG_HEIGHT = 1080 # 图像高度
YUV_FILE_PATH = "./b1f6c/3_gray_noise.yuv" # 您的YUV文件路径
NUM_BENCHMARK_RUNS = 100 # 您希望运行多少次C函数进行测试

# 根据操作系统确定库文件名
if os.name == 'nt': # Windows
    LIB_NAME = 'yuvconverter.dll'
elif os.name == 'posix':
    # Linux or macOS. macOS often uses .dylib, Linux .so
    if os.uname().sysname == 'Darwin': # macOS
        LIB_NAME = 'libyuvconverter.dylib'
    else: # Linux
        LIB_NAME = 'libyuvconverter.so'
else:
    raise OSError("Unsupported OS for ctypes library loading")

# 构造库的完整路径
# 假设库与脚本在同一目录或系统路径中
# 如果库不在标准路径，您需要提供完整路径
# 例如: lib_path = os.path.join(os.path.dirname(__file__), LIB_NAME)
try:
    # 尝试加载库
    # 注意：如果您的 .dll/.so/.dylib 文件与此脚本不在同一目录，
    # 请将 "./{LIB_NAME}" 替换为库文件的确切路径。
    # 例如: yuv_lib = ctypes.CDLL(os.path.join(os.path.dirname(__file__), LIB_NAME))
    # 或者确保库文件在系统的 PATH/LD_LIBRARY_PATH 中。
    lib_path = f"./{LIB_NAME}" # 假设在当前目录
    if not os.path.exists(lib_path) and not os.path.isabs(lib_path):
        # 如果相对路径不存在，尝试在脚本所在目录查找
        script_dir = os.path.dirname(os.path.abspath(__file__))
        lib_path_alt = os.path.join(script_dir, LIB_NAME)
        if os.path.exists(lib_path_alt):
            lib_path = lib_path_alt
        else:
            # 如果脚本目录也没有，尝试让系统自己找
            # 这种情况是假设 LIB_NAME 已经在系统路径中
            # 或者用户通过其他方式确保了库的可访问性
            pass # yuv_lib = ctypes.CDLL(LIB_NAME) 可能会成功

    print(f"尝试加载库: {os.path.abspath(lib_path) if os.path.exists(lib_path) else LIB_NAME}")
    yuv_lib = ctypes.CDLL(lib_path if os.path.exists(lib_path) else LIB_NAME)
except OSError as e:
    print(f"错误: 无法加载共享库 '{LIB_NAME}'. 请确保它已编译并位于正确路径。")
    print(f"尝试的路径: {os.path.abspath(lib_path) if os.path.exists(lib_path) else LIB_NAME}")
    print(f"详细错误: {e}")
    exit()

# --- 定义C函数的参数类型和返回类型 ---
try:
    c_converter_func = yuv_lib.yuv420p_to_rgb_conversion_c
    c_converter_func.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte), # y_data
        ctypes.POINTER(ctypes.c_ubyte), # u_data
        ctypes.POINTER(ctypes.c_ubyte), # v_data
        ctypes.POINTER(ctypes.c_ubyte), # out_rgb_data
        ctypes.c_int,                   # width
        ctypes.c_int                    # height
    ]
    c_converter_func.restype = None # void
except AttributeError as e:
    print(f"错误: 在库 '{LIB_NAME}' 中找不到函数 'yuv420p_to_rgb_conversion_c'。")
    print(f"详细错误: {e}")
    exit()


# --- 读取YUV文件数据 ---
y_plane_size = IMG_WIDTH * IMG_HEIGHT
uv_width = IMG_WIDTH // 2
uv_height = IMG_HEIGHT // 2
uv_plane_size = uv_width * uv_height

print(f"正在读取YUV文件: {YUV_FILE_PATH}")
try:
    with open(YUV_FILE_PATH, 'rb') as f:
        y_data_bytes = f.read(y_plane_size)
        u_data_bytes = f.read(uv_plane_size)
        v_data_bytes = f.read(uv_plane_size)

    if len(y_data_bytes) != y_plane_size or \
       len(u_data_bytes) != uv_plane_size or \
       len(v_data_bytes) != uv_plane_size:
        print(f"错误: YUV文件大小与期望不符。")
        print(f"期望 Y平面大小: {y_plane_size}, 实际: {len(y_data_bytes)}")
        print(f"期望 U平面大小: {uv_plane_size}, 实际: {len(u_data_bytes)}")
        print(f"期望 V平面大小: {uv_plane_size}, 实际: {len(v_data_bytes)}")
        exit()
    print("YUV文件数据读取完毕。")

except FileNotFoundError:
    print(f"错误: YUV文件 '{YUV_FILE_PATH}' 未找到。")
    exit()
except Exception as e:
    print(f"读取YUV文件时发生错误: {e}")
    exit()

# --- 将Python bytes 转换为 ctypes可以使用的类型 ---
# 注意：ctypes.cast 不会复制数据，它只是创建一个指向现有内存的指针。
# 这对于性能是好的，但要确保原始 bytes 对象 (y_data_bytes 等) 在C函数调用期间保持活动状态。
y_data_c = ctypes.cast(y_data_bytes, ctypes.POINTER(ctypes.c_ubyte))
u_data_c = ctypes.cast(u_data_bytes, ctypes.POINTER(ctypes.c_ubyte))
v_data_c = ctypes.cast(v_data_bytes, ctypes.POINTER(ctypes.c_ubyte))

# --- 准备输出缓冲区 ---
# 这个缓冲区会在每次C函数调用时被覆盖
rgb_buffer_size = IMG_WIDTH * IMG_HEIGHT * 3
out_rgb_data_c = (ctypes.c_ubyte * rgb_buffer_size)() # 创建一个ubyte数组

# --- 执行性能测试 ---
print(f"\n开始性能测试，将调用C函数 {NUM_BENCHMARK_RUNS} 次...")
total_time_c_calls = 0
individual_call_times = []

# 预热运行 (可选，但有时有助于获得更稳定的后续测量)
# print("执行一次预热调用...")
# c_converter_func(y_data_c, u_data_c, v_data_c, out_rgb_data_c, IMG_WIDTH, IMG_HEIGHT)
# print("预热调用完成。")

start_benchmark_time = time.perf_counter()

for i in range(NUM_BENCHMARK_RUNS):
    # 如果需要非常精确地测量单次调用，可以将计时器放在循环内部
    # start_call_time = time.perf_counter()
    c_converter_func(
        y_data_c,
        u_data_c,
        v_data_c,
        out_rgb_data_c, # C函数会直接修改这个缓冲区的内容
        IMG_WIDTH,
        IMG_HEIGHT
    )
    # end_call_time = time.perf_counter()
    # call_duration = end_call_time - start_call_time
    # individual_call_times.append(call_duration)
    # total_time_c_calls += call_duration # 如果计时器在循环内，则这样累加

end_benchmark_time = time.perf_counter()
total_time_c_calls = end_benchmark_time - start_benchmark_time # 如果计时器在循环外，则这样计算总时间

print("C函数调用性能测试完成。")

# --- 打印性能测试结果 ---
print("\n--- 性能测试结果 ---")
print(f"总共调用次数: {NUM_BENCHMARK_RUNS}")
print(f"C函数总执行时间: {total_time_c_calls:.6f} 秒")

if NUM_BENCHMARK_RUNS > 0:
    avg_time_per_call = total_time_c_calls / NUM_BENCHMARK_RUNS
    calls_per_second = NUM_BENCHMARK_RUNS / total_time_c_calls if total_time_c_calls > 0 else float('inf')
    print(f"平均每次调用耗时: {avg_time_per_call:.8f} 秒 ({avg_time_per_call * 1000:.4f} 毫秒)")
    print(f"每秒调用次数 (吞吐量): {calls_per_second:.2f} 次/秒")

    # 如果记录了单次调用时间，可以打印更多统计信息
    # if individual_call_times:
    #     min_time = min(individual_call_times)
    #     max_time = max(individual_call_times)
    #     print(f"最快单次调用: {min_time:.8f} 秒 ({min_time * 1000:.4f} 毫秒)")
    #     print(f"最慢单次调用: {max_time:.8f} 秒 ({max_time * 1000:.4f} 毫秒)")
else:
    print("没有执行任何测试调用。")


# --- 处理最后一次调用的结果 (例如，保存为Pillow图像) ---
# out_rgb_data_c 现在包含最后一次C函数调用的结果
print("\n正在处理最后一次转换的结果...")
# 将ctypes ubyte数组转换回Python bytes对象
# 这一步会复制数据，如果只为了保存图片，这是必要的。
rgb_result_bytes = bytes(out_rgb_data_c)

# (可选) 使用Pillow保存为图像
try:
    from PIL import Image
    print("使用Pillow创建图像对象...")
    # 确保图像模式、尺寸和数据字节长度匹配
    # RGB图像每个像素3字节
    expected_bytes_len = IMG_WIDTH * IMG_HEIGHT * 3
    if len(rgb_result_bytes) != expected_bytes_len:
        print(f"错误: RGB结果字节长度 ({len(rgb_result_bytes)}) 与期望 ({expected_bytes_len}) 不符。")
        print("无法保存图像。")
    else:
        rgb_image = Image.frombytes('RGB', (IMG_WIDTH, IMG_HEIGHT), rgb_result_bytes)
        
        # 从YUV文件名生成输出PNG文件名
        yuv_basename = os.path.basename(YUV_FILE_PATH)
        yuv_name_no_ext = os.path.splitext(yuv_basename)[0]
        output_png_file = f"{yuv_name_no_ext}_{IMG_WIDTH}x{IMG_HEIGHT}_rgb_from_c_final.png"
        
        print(f"正在保存图像到: {output_png_file}")
        rgb_image.save(output_png_file)
        print(f"成功将最后一次转换的RGB数据保存到: {output_png_file}")

except ImportError:
    print("Pillow未安装，无法保存为图像。RGB数据在 'rgb_result_bytes' 变量中。")
    print(f"RGB结果字节长度: {len(rgb_result_bytes)}")
except Exception as e:
    print(f"保存RGB图像时发生错误: {e}")

print("\n脚本执行完毕。")
