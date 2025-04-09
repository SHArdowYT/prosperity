"""
M = [
    1,    1.45, 0.52, 0.72;
    0.7,  1,    0.31, 0.48;
    1.95, 3.1,  1,    1.49;
    1.34, 1.98, 0.64, 1
];

M.*M'

% ans =
%     1.0000    1.0150    1.0140    0.9648
%     1.0150    1.0000    0.9610    0.9504
%     1.0140    0.9610    1.0000    0.9536
%     0.9648    0.9504    0.9536    1.0000
% by inspection 
"""



M = [
    [1,    1.45, 0.52, 0.72],
    [0.7,  1,    0.31, 0.48],
    [1.95, 3.1,  1,    1.49],
    [1.34, 1.98, 0.64, 1]
]


import itertools
combinations = list(itertools.product(range(4, 5), range(1, 5), range(1, 5), range(1, 5), range(1, 5), range(4, 5)))

results = {}

for sequence in combinations:
    product = 1
    for i in range(len(sequence) - 1):
        product *= M[sequence[i] - 1][sequence[i + 1] - 1]
    results[sequence] = product

for sequence, product in sorted(results.items(), key=lambda result: result[1], reverse=True):
    print(f"{' '.join([str(i) for i in sequence])} | {product}")


# most profitable:
# 4 1 3 2 1 4 | 1.08868032