// #include <iostream>

#include <vector>
#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

using namespace std;
namespace py = pybind11;


// typedef typename py::array_t<double, py::array::c_style | py::array::forcecast> py_cdarray_t;

py::array_t<int> equalizeHistogram(py::array_t<int> frame_in, py::ssize_t width,  py::ssize_t height, int max_val = 65535) {
    int total = width * height;
    int n_bins = max_val + 1;
    auto frame_out = py::array_t<int>({total}); // Not sure, but I don't think you need the explicit '{h, 1}'

    // Compute histogram
    vector<int> hist(n_bins, 0);
    for (ssize_t i = 0; i < total; ++i) {
        hist[frame_in.at(i)]++;
    }


    // Build LUT from cumulative histrogram

    // Find first non-zero bin
    int i = 0;
    while (!hist[i]) ++i;

    if (hist[i] == total) {
        for (int j = 0; j < total; ++j) {
            frame_in.mutable_at(j) = i;
        }
        return frame_out;
    }

    // Compute scale
    float scale = (n_bins - 1.f) / (total - hist[i]);

    // Initialize lut
    vector<short> lut(n_bins, 0);
    i++;

    int sum = 0;
    for (; i < hist.size(); ++i) {
        sum += hist[i];
        // the value is saturated in range [0, max_val]
        lut[i] = max(0, min(int(round(sum * scale)), max_val));
    }

    // Apply equalization
    for (int i = 0; i < total; ++i) {
        frame_out.mutable_at(i) = lut[frame_in.at(i)];
    }
    return frame_out;
}

PYBIND11_MODULE(CImageProcessing, m) {
    // hists.doc() = "";
    m.def("equalizeHistogram", &equalizeHistogram, "void equalizeHistogram(short *frame_in, short *frame_out, int width, int height, int max_val = 65535)");
}



//
// range min_max(const long *frame, const size_t N) {
//     range range;
//     range.minimum = 2147483647;
//     range.maximum = -2147483648;
//     for (size_t i = 0; i < N; ++i) {
//         long val = frame[i];
//         if (val < range.minimum) {
//             range.minimum = val;
//         }
//         if (val > range.maximum) {
//             range.maximum = val;
//         }
//     }
//     return range;
// }
//
//
// range percentile(const long *frame, const size_t width, const size_t height) {
//     return min_max(frame, width*height);
//     // for (size_t i = 0; i < width; i++) {
//     //     for (size_t j = 0; j < width; j++) {
//     //         return 0;
//     //     }
//     //     return 0;
//     // }
// }
//
//
//
// //
// hist rescale_percentile(const long *data_in, const size_t width, const size_t height) {
//     const range range = min_max(data_in, width * height);
//
//     frame frame_in;
//     frame_in.data = data_in;
//     frame_in.range = range;
//     frame_in.N = width * height;
//     hist hist;
//
//
//
//     for (size_t i=0; i < range.maximum-range.minimum; ++i) {
//         hist.hist_bins[i] = (long)i;
//         hist.hist_data[i] = 0;
//     }
//
//     for (size_t i = 0; i < frame_in.N; ++i) {
//         const long val = data_in[i];
//         hist.hist_data[val] += 1;
//     }
//
//     return hist;
// }