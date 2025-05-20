import ctypes
import os # 用于路径处理

# --- 配置 ---
IMG_WIDTH = 1920  # 假设的图像宽度
IMG_HEIGHT = 1080 # 假设的图像高度
YUV_FILE_PATH = "./b1f6c/3_gray_noise.yuv" # 您的YUV文件路径

# 根据操作系统确定库文件名
if os.name == 'nt': # Windows
    LIB_NAME = 'yuvconverter.dll'
elif os.name == 'posix':
    # Linux or macOS. macOS often uses .dylib, Linux .so
    # This simple check might need adjustment for macOS specifically if both .so and .dylib exist
    if os.uname().sysname == 'Darwin': # macOS
        LIB_NAME = 'libyuvconverter.dylib'
    else: # Linux
        LIB_NAME = 'libyuvconverter.so'
else:
    raise OSError("Unsupported OS for ctypes library loading")

# 构造库的完整路径 (假设库与脚本在同一目录或系统路径中)
# 您可能需要根据实际库文件位置调整此路径
try:
    # 尝试加载库
    # 如果库不在标准路径，您需要提供完整路径
    # e.g., lib_path = os.path.join(os.path.dirname(__file__), LIB_NAME)
    # yuv_lib = ctypes.CDLL(lib_path)
    yuv_lib = ctypes.CDLL(f"./{LIB_NAME}") # 假设在当前目录
except OSError as e:
    print(f"错误: 无法加载共享库 '{LIB_NAME}'. 请确保它已编译并位于正确路径。")
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


# --- 读取YUV文件数据 (与您原Python脚本类似) ---
y_plane_size = IMG_WIDTH * IMG_HEIGHT
uv_width = IMG_WIDTH // 2
uv_height = IMG_HEIGHT // 2
uv_plane_size = uv_width * uv_height

try:
    with open(YUV_FILE_PATH, 'rb') as f:
        y_data_bytes = f.read(y_plane_size)
        u_data_bytes = f.read(uv_plane_size)
        v_data_bytes = f.read(uv_plane_size)

    if len(y_data_bytes) != y_plane_size or \
       len(u_data_bytes) != uv_plane_size or \
       len(v_data_bytes) != uv_plane_size:
        print("错误: YUV文件大小与期望不符。")
        exit()

except FileNotFoundError:
    print(f"错误: YUV文件 '{YUV_FILE_PATH}' 未找到。")
    exit()
except Exception as e:
    print(f"读取YUV文件时发生错误: {e}")
    exit()

# --- 将Python bytes 转换为 ctypes可以使用的类型 ---
y_data_c = ctypes.cast(y_data_bytes, ctypes.POINTER(ctypes.c_ubyte))
u_data_c = ctypes.cast(u_data_bytes, ctypes.POINTER(ctypes.c_ubyte))
v_data_c = ctypes.cast(v_data_bytes, ctypes.POINTER(ctypes.c_ubyte))

# --- 准备输出缓冲区 ---
rgb_buffer_size = IMG_WIDTH * IMG_HEIGHT * 3
out_rgb_data_c = (ctypes.c_ubyte * rgb_buffer_size)() # 创建一个ubyte数组

# --- 调用C函数 ---
print("调用C函数进行转换...")
c_converter_func(
    y_data_c,
    u_data_c,
    v_data_c,
    out_rgb_data_c,
    IMG_WIDTH,
    IMG_HEIGHT
)
print("C函数调用完成。")

# --- 处理结果 (例如，保存为Pillow图像) ---
# 将ctypes ubyte数组转换回Python bytes对象
rgb_result_bytes = bytes(out_rgb_data_c)

# (可选) 使用Pillow保存为图像
try:
    from PIL import Image
    rgb_image = Image.frombytes('RGB', (IMG_WIDTH, IMG_HEIGHT), rgb_result_bytes)
    output_png_file = os.path.splitext(os.path.basename(YUV_FILE_PATH))[0] + \
                      f"_{IMG_WIDTH}x{IMG_HEIGHT}_rgb_from_c.png"
    rgb_image.save(output_png_file)
    print(f"成功将转换后的RGB数据保存到: {output_png_file}")
except ImportError:
    print("Pillow未安装，无法保存为图像。RGB数据在 'rgb_result_bytes' 中。")
except Exception as e:
    print(f"保存RGB图像时发生错误: {e}")

