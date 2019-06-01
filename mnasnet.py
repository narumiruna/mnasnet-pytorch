from torch import nn


class ConvBNReLU(nn.Sequential):

    def __init__(self, in_planes, out_planes, kernel_size=1, stride=1, groups=1):
        padding = (kernel_size - 1) // 2
        super(ConvBNReLU, self).__init__(
            nn.Conv2d(in_planes, out_planes, kernel_size, stride=stride, padding=padding, groups=groups, bias=False),
            nn.BatchNorm2d(out_planes),
            nn.ReLU(inplace=True),
        )


class SqueezeExcitation(nn.Module):

    def __init__(self, num_features, reduced_dim):
        super(SqueezeExcitation, self).__init__()
        self.se = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(num_features, reduced_dim, 1, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(reduced_dim, num_features, 1, bias=True),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return x * self.se(x)


class MBConvBlock(nn.Module):

    def __init__(self, in_planes, out_planes, stride, expand_ratio, kernel_size=3, reduction_ratio=1, no_skip=False):
        super(MBConvBlock, self).__init__()
        self.use_residual = in_planes == out_planes and stride == 1 and not no_skip
        assert stride in [1, 2]
        assert kernel_size in [3, 5]

        hidden_dim = int(in_planes * expand_ratio)
        layers = []

        # pw
        if in_planes != hidden_dim:
            layers += [ConvBNReLU(in_planes, hidden_dim, kernel_size=1)]

        # dw
        layers += [ConvBNReLU(hidden_dim, hidden_dim, kernel_size, stride=stride, groups=hidden_dim)]

        # se
        if reduction_ratio != 1:
            reduced_dim = max(1, int(in_planes / reduction_ratio))
            layers += [SqueezeExcitation(hidden_dim, reduced_dim)]

        # pw-linear
        layers += [
            nn.Conv2d(hidden_dim, out_planes, 1, bias=False),
            nn.BatchNorm2d(out_planes),
        ]

        self.conv = nn.Sequential(*layers)

    def forward(self, x):
        if self.use_residual:
            return x + self.conv(x)
        else:
            return self.conv(x)


class MnasNetA1(nn.Module):

    def __init__(self, width_mult=1.0, num_classes=1000):
        super(MnasNetA1, self).__init__()

        settings = [
            # t, c, n, s, k, r
            [1, 16, 1, 1, 3, 1],  # SepConv_3x3
            [6, 24, 2, 2, 3, 1],  # MBConv6_3x3
            [3, 40, 3, 2, 5, 4],  # MBConv3_5x5, SE
            [6, 80, 4, 2, 3, 1],  # MBConv6_3x3
            [6, 112, 2, 1, 3, 4],  # MBConv6_3x3, SE
            [6, 160, 3, 2, 5, 4],  # MBConv6_5x5, SE
            [6, 320, 1, 1, 3, 1]  # MBConv6_3x3
        ]

        features = [ConvBNReLU(3, int(32 * width_mult), 3, stride=2)]

        in_channels = int(32 * width_mult)
        for i, (t, c, n, s, k, r) in enumerate(settings):
            out_channels = int(c * width_mult)
            no_skip = True if i == 0 else False
            for j in range(n):
                stride = s if j == 0 else 1
                features += [
                    MBConvBlock(
                        in_channels, out_channels, stride, t, kernel_size=k, reduction_ratio=r, no_skip=no_skip)
                ]
                in_channels = out_channels

        features += [ConvBNReLU(in_channels, 1280, kernel_size=1)]
        self.features = nn.Sequential(*features)
        self.avg_pool = nn.AvgPool2d(kernel_size=7)
        self.classifier = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(1280, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = self.avg_pool(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


def numel(model: nn.Module):
    return sum(p.numel() for p in model.parameters())


def main():
    import torch
    m = MnasNetA1(width_mult=1.0)
    x = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        y = m(x)
        print(y.size())

    print(numel(m))


if __name__ == "__main__":
    main()
