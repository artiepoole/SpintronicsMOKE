#include <vector>
#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

using namespace std;
namespace py = pybind11;

py::array_t<uint16_t> equalizeHistogram(const py::array_t<uint16_t> &frame_in) {
    constexpr int max_val = 65535;
    py::ssize_t width = frame_in.shape(0);
    py::ssize_t height = frame_in.shape(1);
    const long total = width * height;
    constexpr long n_bins = max_val + 1;
    auto frame_out = py::array_t<uint16_t>({width, height});
    vector<int> new_level(n_bins, 0);

    // Counts the number of pixels in each brightness
    vector<int> hist(n_bins, 0);

    #pragma omp parallel for
    for (int ij = 0; ij < total; ++ij){
        hist[frame_in.at(ij / height, ij % height)]++;
    }
    // Calculates a new brightness based on the histogram such that the cumulative distribution function is as linear as possible.
    long sum = 0;
    for (int i = 0; i < n_bins; ++i) {
        sum += hist[i];
        new_level[i] = round(n_bins * (sum * 1.0f / total));
    }

    // Assigns new brightness based on original brightness and the new CDF
    #pragma omp parallel for
    for (int ij = 0; ij < total; ++ij){
        frame_out.mutable_at(ij / height, ij % height) = new_level[frame_in.at(ij / height, ij % height)];
    }
    return frame_out;
}

py::array_t<uint16_t> integer_mean(const py::array_t<uint16_t> &stack_in) {
    const int n_frames = stack_in.shape(0);
    const py::ssize_t width = stack_in.shape(1);
    const py::ssize_t height = stack_in.shape(2);
    auto frame_out = py::array_t<uint16_t>({width, height});

    #pragma omp parallel for
    for (int ij = 0; ij < width*height; ++ij){
        int sum = 0;
        for (int frame = 0; frame < n_frames; ++frame) {
            sum += stack_in.at(frame, ij/height, ij%height);
        }
        frame_out.mutable_at(ij/height, ij%height) += sum / n_frames;
    }

    return frame_out;
}

py::array_t<uint16_t> basic_exposure(const py::array_t<uint16_t> &frame_in, const int &frame_max) {
    constexpr int type_max = 65535;
    py::ssize_t width = frame_in.shape(0);
    py::ssize_t height = frame_in.shape(1);
    auto frame_out = py::array_t<uint16_t>({width, height});

    #pragma omp parallel for
    for (int ij = 0; ij < width*height; ++ij){
            frame_out.mutable_at(ij/height, ij%height) = frame_in.at(ij/height, ij%height) * (type_max / frame_max);
    }
    return frame_out;
}


PYBIND11_MODULE(CImageProcessing, m) {
    m.def("equalizeHistogram", &equalizeHistogram,
          "py::array_t<int> & equalizeHistogram(const py::array_t<int> & frame_in)");
    m.def("integer_mean", &integer_mean,
          "py::array_t<int> & integer_mean(const py::array_t<int> & frame_in)");
    m.def("basic_exposure", &basic_exposure,
          "py::array_t<int> & basic_exposure(const py::array_t<int> & frame_in, const int &frame_max)");
}
