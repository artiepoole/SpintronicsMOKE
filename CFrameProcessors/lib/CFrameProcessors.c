#include "CFrameProcessors.h"

#include <stddef.h>


range min_max(const long *frame, const size_t N) {
    range range;
    range.minimum = 2147483647;
    range.maximum = -2147483648;
    for (size_t i = 0; i < N; ++i) {
        long val = frame[i];
        if (val < range.minimum) {
            range.minimum = val;
        }
        if (val > range.maximum) {
            range.maximum = val;
        }
    }
    return range;
}


range percentile(const long *frame, const size_t width, const size_t height) {
    return min_max(frame, width*height);
    // for (size_t i = 0; i < width; i++) {
    //     for (size_t j = 0; j < width; j++) {
    //         return 0;
    //     }
    //     return 0;
    // }
}



//
hist rescale_percentile(const long *data_in, const size_t width, const size_t height) {
    const range range = min_max(data_in, width * height);

    frame frame_in;
    frame_in.data = data_in;
    frame_in.range = range;
    frame_in.N = width * height;
    hist hist;



    for (size_t i=0; i < range.maximum-range.minimum; ++i) {
        hist.hist_bins[i] = (long)i;
        hist.hist_data[i] = 0;
    }

    for (size_t i = 0; i < frame_in.N; ++i) {
        const long val = data_in[i];
        hist.hist_data[val] += 1;
    }

    return hist;
}
