# Mathematical
import numpy as np
from scipy.ndimage.interpolation import map_coordinates

# Pytorch
import torch
from torch.utils import data
from torchvision import datasets

# Misc
from functools import lru_cache


def genuv(h, w):
    u, v = np.meshgrid(np.arange(w), np.arange(h))
    u = (u + 0.5) * 2 * np.pi / w - np.pi
    v = (v + 0.5) * np.pi / h - np.pi / 2
    return np.stack([u, v], axis=-1)


def uv2img_idx(uv, h, w, u_fov, v_fov):
    assert 0 < u_fov and u_fov < np.pi
    assert 0 < v_fov and v_fov < np.pi
    
    x = np.tan(uv[..., 0])
    y = np.tan(uv[..., 1]) / np.cos(uv[..., 0])
    x = x * w / (2 * np.tan(u_fov / 2)) + w / 2
    y = y * h / (2 * np.tan(v_fov / 2)) + h / 2

    invalid = (uv[..., 0] < -u_fov / 2) | (uv[..., 0] > u_fov / 2) |\
              (uv[..., 1] < -v_fov / 2) | (uv[..., 1] > v_fov / 2)
    x[invalid] = -100
    y[invalid] = -100
    
    return np.stack([y, x], axis=0)


class OmniDataset(data.Dataset):
    def __init__(self, dataset, fov=120, outshape=(60, 60),
                 flip=False, h_rotate=False,
                 img_mean=None, img_std=None):
        '''
        Convert classification dataset to omnidirectional version
        @dataset  dataset with same interface as torch.utils.data.Dataset
                  yield (PIL image, label) if indexing
        '''
        self.dataset = dataset
        self.fov = fov
        self.outshape = outshape
        self.flip = flip
        self.h_rotate = h_rotate
        self.img_mean = img_mean
        self.img_std = img_std

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        img = np.array(self.dataset[idx][0], np.float32)
        h, w = img.shape[:2]
        uv = genuv(*self.outshape)
        fov = self.fov * np.pi / 180

        img_idx = uv2img_idx(uv, h, w, fov, fov)
        x = map_coordinates(img, img_idx, order=1)

        # Random flip
        if self.flip and np.random.randint(2) == 0:
            x = np.flip(x, axis=1)

        # Random horizontal rotate
        if self.h_rotate:
            dx = np.random.randint(x.shape[1])
            x = np.roll(x, dx, axis=1)

        # Normalize image
        if self.img_mean is not None:
            x = x - self.img_mean
        if self.img_std is not None:
            x = x / self.img_std

        return torch.FloatTensor(x.copy()), self.dataset[idx][1]


class OmniMNIST(OmniDataset):
    def __init__(self, root='datas/MNIST', train=True,
                 download=True, *args, **kwargs):
        '''
        Omnidirectional MNIST
        @root (str)       root directory storing the dataset
        @train (bool)     train or test split
        @download (bool)  whether to download if data now exist
        '''
        self.MNIST = datasets.MNIST(root, train=train, download=download)
        super(OmniMNIST, self).__init__(self.MNIST, *args, **kwargs)


if __name__ == '__main__':

    import os
    import argparse
    from PIL import Image

    parser = argparse.ArgumentParser()
    parser.add_argument('--idx', nargs='+', required=True)
    parser.add_argument('--out_dir', default='datas/demo')

    parser.add_argument('--flip', action='store_true')
    parser.add_argument('--h_rotate', action='store_true')
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    dataset = OmniMNIST(flip=args.flip, h_rotate=args.h_rotate)
    for idx in args.idx:
        idx = int(idx)
        path = os.path.join(args.out_dir, '%d.png' % idx)
        x, label = dataset[idx]

        print(path, label)
        Image.fromarray(x.numpy().astype(np.uint8)).save(path)
