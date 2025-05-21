#include <algorithm>
#include <cstddef>
#include <vector>
#include <xmmintrin.h>

using byte = std::byte;
struct RGBPixel_vec {
    __m128i r;
    __m128i g;
    __m128i b;
};

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

RGBPixel_vec ycbcr_to_rgb(__m128& y_float_vec , int u, int v);

void store_single_pixel_raw(
    std::vector<unsigned char>& rgb_byte_array,
    int r_val,
    int g_val,
    int b_val,
    int base_idx
);


RGBPixel_vec ycbcr_to_rgb(__m128& y_float_vec , int u, int v) {
    RGBPixel_vec rgb;
    float v_float = static_cast<float>(v) - 128.0f;
    float u_float = static_cast<float>(u) - 128.0f;
    __m128 u_float_vec = _mm_set1_ps(u_float);
    __m128 v_float_vec = _mm_set1_ps(v_float);

    auto cal_rgb_r = [&y_float_vec, &v_float_vec]() -> __m128i {
        __m128 temp_f = _mm_add_ps(y_float_vec, _mm_mul_ps(v_float_vec, _mm_set1_ps(1.402f)));
        temp_f = _mm_max_ps(temp_f, _mm_setzero_ps());      // max(val, 0.0f)
        temp_f = _mm_min_ps(temp_f, _mm_set1_ps(255.0f)); // min(val, 255.0f)
        return _mm_cvtps_epi32(temp_f);
    };

    auto cal_rgb_g = [&y_float_vec, &v_float_vec, &u_float_vec]() -> __m128i {
        __m128 temp_f = _mm_sub_ps(y_float_vec, _mm_mul_ps(u_float_vec, _mm_set1_ps(0.344136f)));
        temp_f = _mm_sub_ps(temp_f, _mm_mul_ps(v_float_vec, _mm_set1_ps(0.714136f)));
        temp_f = _mm_max_ps(temp_f, _mm_setzero_ps());      // max(val, 0.0f)
        temp_f = _mm_min_ps(temp_f, _mm_set1_ps(255.0f)); // min(val, 255.0f)
        return _mm_cvtps_epi32(temp_f);
    };

    auto cal_rgb_b = [&y_float_vec, &u_float_vec]() -> __m128i {
        __m128 temp_f = _mm_add_ps(y_float_vec, _mm_mul_ps(u_float_vec, _mm_set1_ps(1.772f)));
        temp_f = _mm_max_ps(temp_f, _mm_setzero_ps());      // max(val, 0.0f)
        temp_f = _mm_min_ps(temp_f, _mm_set1_ps(255.0f)); // min(val, 255.0f)
        return _mm_cvtps_epi32(temp_f);
    };

    rgb.r = cal_rgb_r();
    rgb.g = cal_rgb_g();
    rgb.b = cal_rgb_b();

    return rgb;
}


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
    int uv_height = height / 2;
    int current_byte_index = 0; // 当前在rgb_byte_array中的索引

    for (int uv_r = 0; uv_r < uv_height; ++uv_r) {
        for (int uv_c = 0; uv_c < uv_width; ++uv_c) {

            int y_pixel_index = uv_r * 2 * width + uv_c * 2; // Y 平面像素索引

            // __m128 y_float_vec;  
            float y_buffer[4];
            int y_r0 = uv_r * 2;
            int y_r1 = y_r0 + 1;
            int y_c0 = uv_c * 2;
            int y_c1 = y_c0 + 1;
            // u v 方向上的元素数量是y方向元素数量的1/4 其长宽索引都少50%
            // u[x,y] 对应 y[2x,2y] y[2x+1,2y] y[2x,2y+1] y[2x+1,2y+1]

            y_buffer[0] = static_cast<float>(y_data[y_r0 * width + y_c0]);
            y_buffer[1] = (y_c1 < width) ? static_cast<float>(y_data[y_r0 * width + y_c1]) : y_buffer[0]; // 或0.0f
            if (y_r1 < height) {
                y_buffer[2] = static_cast<float>(y_data[y_r1 * width + y_c0]);
                y_buffer[3] = (y_c1 < width) ? static_cast<float>(y_data[y_r1 * width + y_c1]) : y_buffer[2]; // 或0.0f
            } else { // 整个下一行Y值都超出了图像高度
                y_buffer[2] = y_buffer[0]; // 或0.0f
                y_buffer[3] = y_buffer[1]; // 或0.0f
            }
            __m128 y_float_vec = _mm_loadu_ps(y_buffer);

            int uv_pixel_index = uv_r * uv_width + uv_c; // U 平面像素索引
            int u_pixel = u_data[uv_pixel_index]; // U 平面像素值
            int v_pixel = v_data[uv_pixel_index]; // V 平面像素值

            // 将 YUV 转换为 RGB
            RGBPixel_vec rgb_pixel = ycbcr_to_rgb(y_float_vec, u_pixel, v_pixel);

                        int r_vals[4], g_vals[4], b_vals[4];
            _mm_storeu_si128((__m128i*)r_vals, rgb_pixel.r);
            _mm_storeu_si128((__m128i*)g_vals, rgb_pixel.g);
            _mm_storeu_si128((__m128i*)b_vals, rgb_pixel.b);
            
            // 计算2x2块中四个像素在目标RGB数组中的起始索引
            // y_r0, y_c0, y_r1, y_c1 已在Y值加载部分定义

            // 像素 (y_c0, y_r0) -> r_vals[0], g_vals[0], b_vals[0]
            if (y_r0 < height && y_c0 < width) { // 边界检查
                int base_idx00 = (y_r0 * width + y_c0) * 3;
                store_single_pixel_raw(rgb_byte_array, r_vals[0], g_vals[0], b_vals[0],base_idx00);
            }

            // 像素 (y_c1, y_r0) -> r_vals[1], g_vals[1], b_vals[1]
            if (y_r0 < height && y_c1 < width) { // 边界检查
                int base_idx01 = (y_r0 * width + y_c1) * 3;
                store_single_pixel_raw(rgb_byte_array, r_vals[1], g_vals[1], b_vals[1],base_idx01);
            }

            // 像素 (y_c0, y_r1) -> r_vals[2], g_vals[2], b_vals[2]
            if (y_r1 < height && y_c0 < width) { // 边界检查
                int base_idx10 = (y_r1 * width + y_c0) * 3;
                store_single_pixel_raw(rgb_byte_array, r_vals[2], g_vals[2], b_vals[2],base_idx10);
            }

            // 像素 (y_c1, y_r1) -> r_vals[3], g_vals[3], b_vals[3]
            if (y_r1 < height && y_c1 < width) { // 边界检查
                int base_idx11 = (y_r1 * width + y_c1) * 3;
                store_single_pixel_raw(rgb_byte_array, r_vals[3], g_vals[3], b_vals[3],base_idx11);
            }
        }
    }
    return rgb_byte_array;
}


void store_single_pixel_raw(
    std::vector<unsigned char>& rgb_byte_array,
    int r_val,
    int g_val,
    int b_val,
    int base_idx
) {
    // 调用者负责边界检查 本函数不负责
    rgb_byte_array[base_idx + 0] = static_cast<unsigned char>(r_val);
    rgb_byte_array[base_idx + 1] = static_cast<unsigned char>(g_val);
    rgb_byte_array[base_idx + 2] = static_cast<unsigned char>(b_val);
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