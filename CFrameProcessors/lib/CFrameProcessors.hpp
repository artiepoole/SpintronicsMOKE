#ifndef CIMAGEPROCESSING_LIBRARY_H
#define CIMAGEPROCESSING_LIBRARY_H



//
// typedef struct range {
//     long minimum;
//     long maximum;
// } range;
//
// typedef struct frame {
//     const long *data;
//     size_t N;
//     range range;
// } frame;
//
// typedef struct hist {
//     long hist_data[65536];
//     long hist_bins[65536];
// } hist;
//
// range min_max(const long *frame, const size_t N);
//
// range percentile(const long *frame, const size_t width, const size_t height);
//
// hist rescale_percentile(const long *data_in, size_t width, size_t height);
//

extern "C"
void equalizeHistogram(short * pdata, int  width, int  height, int  max_val);
#endif //CIMAGEPROCESSING_LIBRARY_H