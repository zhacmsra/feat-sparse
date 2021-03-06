'''ResNet in PyTorch.

For Pre-activation ResNet, see 'preact_resnet.py'.

Reference:
[1] Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun
    Deep Residual Learning for Image Recognition. arXiv:1512.03385
'''
import torch
import torch.nn as nn
import torch.nn.functional as F

model_urls = {
        'resnet18': 'https://download.pytorch.org/models/resnet18-5c106cde.pth',
        'resnet34': 'https://download.pytorch.org/models/resnet34-333f7ec4.pth',
        'resnet50': 'https://download.pytorch.org/models/resnet50-19c8e357.pth',
        'resnet101': 'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth',
        'resnet152': 'https://download.pytorch.org/models/resnet152-b121ed2d.pth',
    }


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes, planes, stride=1):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        self.count_zero(out)

        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = F.relu(out)
        self.count_zero(out)
        return out

    def count_zero(self, arr):
        X, Y, W, Z = arr.size()
        lw = 0
        lw10 = 0
        for i in range(0, Y):
            cnt = float(torch.nonzero(arr[0][i][:][:]).size(0))/float(W*Z)
            print("{0:.2f}, ".format(cnt), end="") 
            if cnt == 0.0:
                lw = lw + 1
            if cnt <= 0.10 and cnt != 0:
                lw10 = lw10 + 1
            if (i+1)%20 == 0:
                print("\n", end="")
        print(arr.size())
        print("\n(featuremap-wise all-zeros: {0:d}/{1:d}={2:0.4f}) ".format(lw, Y, float(lw)/float(Y)))
        print("(featuremap-wise 0.1 non-zeros: {0:d}/{1:d}={2:0.4f}) ".format(lw10, Y, float(lw10)/float(Y)))
        print("(layer-wise non-zeros: {})".format(float(torch.nonzero(arr[0][:][:][:]).size(0))/float(Y*W*Z)))
        #print("number of non-zeros ===> : {0:7.0f} || {1:7.0f} || ratio: {2:.3f}".format(cnt, X*Y*W*Z, float(cnt)/float(X*Y*W*Z)))


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_planes, planes, stride=1):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, self.expansion*planes, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(self.expansion*planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = F.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class ResNet(nn.Module):
    def __init__(self, block, num_blocks, num_classes=10):
        super(ResNet, self).__init__()
        self.in_planes = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.layer1 = self._make_layer(block, 64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(block, 128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(block, 256, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(block, 512, num_blocks[3], stride=2)
        self.linear = nn.Linear(512*block.expansion, num_classes)

    def _make_layer(self, block, planes, num_blocks, stride):
        strides = [stride] + [1]*(num_blocks-1)
        layers = []
        for stride in strides:
            layers.append(block(self.in_planes, planes, stride))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)
        self.print_featmap(out)

        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = F.avg_pool2d(out, 4)
        out = out.view(out.size(0), -1)
        out = self.linear(out)

        return out

    def print_featmap(self, feats):
        def pf(sp, W, X, Y, arr):
            f = open("feat.txt", 'a')
            f.write("sparsity: {}/100: {}x{}x{}\n".format(sp, W, X, Y))
            for i in range(0, X):
                for j in range(0, Y):
                    if arr[i][j].item() == 0.0:
                        f.write("0, ")
                    else:
                        f.write("1, ")
                f.write("\n")
            f.write("\n\n\n")
            f.close()

        _, W, X, Y = feats.size()
        for i in range(0,W):
            sp = torch.nonzero(feats[0][i][:][:]).size(0)*100/(X*Y)
            if ((sp > 45) and (sp < 55)) or ((sp != 0) and (sp < 10)) or (sp > 80) :  
                pf(sp, i, X, Y, feats[0][i][:][:]) #0.5
                continue



def ResNet18():
    return ResNet(BasicBlock, [2,2,2,2])

def ResNet34():
    return ResNet(BasicBlock, [3,4,6,3])

def ResNet50():
    return ResNet(Bottleneck, [3,4,6,3])

def ResNet101():
    return ResNet(Bottleneck, [3,4,23,3])

def ResNet152():
    return ResNet(Bottleneck, [3,8,36,3])


def test():
    net = ResNet18()
    y = net(torch.randn(1,3,32,32))
    print(y.size())

# test()
