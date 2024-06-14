#include <vector>
#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

using namespace std;
namespace py = pybind11;

py::array_t<int> equalizeHistogram(const py::array_t<int> &frame_in) {
    constexpr int max_val = 65535;
    py::ssize_t width = frame_in.shape(0);
    py::ssize_t height = frame_in.shape(1);
    const long total = width * height;
    constexpr long n_bins = max_val + 1;
    auto frame_out = py::array_t<int>({width, height});
    vector<int> new_level(n_bins, 0);

    // Counts the number of pixels in each brightness
    vector<int> hist(n_bins, 0);

    #pragma omp parallel for
    for (ssize_t i = 0; i < width; ++i) {
        for (ssize_t j = 0; j < height; ++j) {
            hist[frame_in.at(i, j)]++;
        }
    }
    // Calculates a new brightness based on the histogram such that the cumulative distribution function is as linear as possible.
    long sum = 0;
    for (int i = 0; i < n_bins; ++i) {
        sum += hist[i];
        new_level[i] = round(n_bins * (sum * 1.0f / total));
    }

    // Assigns new brightness based on original brightness and the new CDF
    #pragma omp parallel for
    for (int i = 0; i < width; ++i) {
        for (int j = 0; j < height; ++j)
            frame_out.mutable_at(i, j) = new_level[frame_in.at(i, j)];
    }
    return frame_out;
}

PYBIND11_MODULE(CImageProcessing, m) {
    m.def("equalizeHistogram", &equalizeHistogram,
          "py::array_t<int> & equalizeHistogram(const py::array_t<int> & frame_in)");
}
