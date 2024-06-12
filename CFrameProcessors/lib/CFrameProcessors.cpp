// #include <iostream>

#include <vector>
#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

using namespace std;
namespace py = pybind11;


// typedef typename py::array_t<double, py::array::c_style | py::array::forcecast> py_cdarray_t;

py::array_t<int> equalizeHistogram(py::array_t<int> frame_in) {
    int max_val = 65535;
    py::ssize_t width = frame_in.shape(0);
    py::ssize_t height = frame_in.shape(1);
    py::ssize_t total = width * height;
    int64_t n_bins = max_val + 1;
    auto frame_out = py::array_t<int>({width, height});

    // Compute histogram
    vector<int> hist(n_bins, 0);
    for (ssize_t i = 0; i < width; ++i) {
        for (ssize_t j = 0; j < height; ++j) {
            hist[frame_in.at(i, j)]++;
        }
    }

    // Initialize lut
    vector<int> new_level(n_bins, 0);

    int64_t sum = 0;
    for (int i = 0; i < n_bins; ++i) {
        sum += hist[i];
        // the value is saturated in range [0, max_val]
        new_level[i] = round(n_bins * sum / total);
    }

    // Apply equalization
    for (int i = 0; i < width; ++i) {
        for (int j = 0; j < height; ++j)
            frame_out.mutable_at(i, j) = new_level[frame_in.at(i, j)];
    }
    return frame_out;
}

PYBIND11_MODULE(CImageProcessing, m) {
    // hists.doc() = "";
    m.def("equalizeHistogram", &equalizeHistogram,
          "void equalizeHistogram(short *frame_in, short *frame_out, int width, int height, int max_val = 65535)");
}
