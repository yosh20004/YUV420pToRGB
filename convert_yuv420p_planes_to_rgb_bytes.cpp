#include <algorithm>
#include <cstddef>
#include <vector>

struct RGBPixel {
    unsigned char r;
    unsigned char g;
    unsigned char b;
};


RGBPixel ycbcr_to_rgb(int y, int u, int v) {
    RGBPixel rgb;
    float y_float = static_cast<float>(y);
    float u_float = static_cast<float>(u) - 128.0f;
    float v_float = static_cast<float>(v) - 128.0f;

    rgb.r = static_cast<unsigned char>(std::clamp(y_float + 1.402f * v_float, 0.0f, 255.0f));
    rgb.g = static_cast<unsigned char>(std::clamp(y_float - 0.344136f * u_float - 0.714136f * v_float, 0.0f, 255.0f));
    rgb.b = static_cast<unsigned char>(std::clamp(y_float + 1.772f * u_float, 0.0f, 255.0f));

    return rgb;
}

using byte = std::byte;
std::vector<unsigned char> __convert_yuv420p_planes_to_rgb_bytes(
    const unsigned char* y_data, // 指向 Y 平面数据的指针
    const unsigned char* u_data, // 指向 U 平面数据的指针
    const unsigned char* v_data, // 指向 V 平面数据的指针
    size_t y_data_size,          // Y 平面数据的大小 (字节数)
    size_t u_data_size,          // U 平面数据的大小 (字节数)
    size_t v_data_size,          // V 平面数据的大小 (字节数)
    int width,                   // 图像宽度
    int height                   // 图像高度
);

std::vector<unsigned char> __convert_yuv420p_planes_to_rgb_bytes(
    const unsigned char* y_data, // 指向 Y 平面数据的指针
    const unsigned char* u_data, // 指向 U 平面数据的指针
    const unsigned char* v_data, // 指向 V 平面数据的指针
    size_t y_data_size,          // Y 平面数据的大小 (字节数)
    size_t u_data_size,          // U 平面数据的大小 (字节数)
    size_t v_data_size,          // V 平面数据的大小 (字节数)
    int width,                   // 图像宽度
    int height                   // 图像高度
) 
{
    std::vector<unsigned char> rgb_byte_array(width * height * 3); // RGB 数据的大小 (字节数)
    int uv_width = width / 2;
    int current_byte_index = 0; // 当前在rgb_byte_array中的索引

    for (int r_idx = 0; r_idx < height; ++r_idx) {
        for (int c_idx = 0; c_idx < width; ++c_idx) {
            
            int y_pixel_index = r_idx * width + c_idx; // Y 平面像素索引
            int y_pixel = y_data[y_pixel_index]; // Y 平面像素值

            int uv_r = r_idx / 2; // U 平面行索引
            int uv_c = c_idx / 2; // U 平面列索引
            int uv_pixel_index = uv_r * uv_width + uv_c; // U 平面像素索引
            int u_pixel = u_data[uv_pixel_index]; // U 平面像素值
            int v_pixel = v_data[uv_pixel_index]; // V 平面像素值

            // 将 YUV 转换为 RGB
            RGBPixel rgb_pixel = ycbcr_to_rgb(y_pixel, u_pixel, v_pixel);
            rgb_byte_array[current_byte_index++] = rgb_pixel.r; // R 分量
            rgb_byte_array[current_byte_index++] = rgb_pixel.g; // G 分量
            rgb_byte_array[current_byte_index++] = rgb_pixel.b; // B 分量
        }
    }
    return rgb_byte_array;
}


extern "C" {
    void yuv420p_to_rgb_conversion_c(
        const unsigned char* y_data,    // 指向 Y 平面数据的指针
        const unsigned char* u_data,    // 指向 U 平面数据的指针
        const unsigned char* v_data,    // 指向 V 平面数据的指针
        unsigned char* out_rgb_data,    // 指向输出RGB数据的缓冲区 (由调用者分配)
        int width,                      // 图像宽度
        int height                      // 图像高度
    ) {
        // 根据YUV420p格式，计算各个平面期望的大小
        // 这些大小主要用于传递给内部函数，内部函数可以根据这些大小进行校验（如果需要）
        size_t y_plane_expected_size = static_cast<size_t>(width) * height;
        size_t uv_width = width / 2;
        size_t uv_height = height / 2;
        size_t uv_plane_expected_size = uv_width * uv_height;

        // 调用C++转换函数
        std::vector<unsigned char> rgb_vector = __convert_yuv420p_planes_to_rgb_bytes(
            y_data, u_data, v_data,
            y_plane_expected_size, uv_plane_expected_size, uv_plane_expected_size,
            width, height
        );

        // 将结果从 std::vector 复制到调用者提供的 out_rgb_data 缓冲区
        if (!rgb_vector.empty() && out_rgb_data != nullptr) {
            // 确保复制的字节数不超过目标缓冲区的大小（隐式假设为 width*height*3）
            // 也不能超过源 vector 的大小
            size_t bytes_to_copy = std::min(rgb_vector.size(), static_cast<size_t>(width * height * 3));
            std::copy(rgb_vector.data(), rgb_vector.data() + bytes_to_copy, out_rgb_data);
        }
    }
}