//
// Created by User on 10/05/2024.
//
#include "generate_hist.h"


void main() {
    const size_t N = 100;
    long data[100];
    long counter = 0;

    for (size_t i = 0; i < N; ++i) {
        data[i] = i % 10 * 10;
    }

    data[99] = 1000;
    data[7] = 5;

    range range = min_max(data, N);

    printf("minimum: %ld\n", range.minimum);
    printf("maximum: %ld\n", range.maximum);

    const hist hist = rescale_percentile(data, 10, 10);
    long trimmed_hist_data[range.maximum+1-range.minimum];

    for (size_t i = range.minimum; i < range.maximum+1; ++i) {
        if (hist.hist_data[i] > 0){
            counter+=1;
        }
    }


}
