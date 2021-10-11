from collections import OrderedDict
from typing import List

from torch import nn, optim
from torch.utils.data import DataLoader


class AutoEncoder(nn.Module):
    def __init__(self, input_dim: int):
        super(AutoEncoder, self).__init__()

        self.input_dim = input_dim
        self.latent_dim = 32
        self.epochs = 200
        self.batch_size = 128
        self.learning_rate = 1e-1
        self.weight_decay = 1e-8
        self.layers_count = 2

        assert self.latent_dim < self.input_dim

        dim_delta = (self.input_dim - self.latent_dim) // self.layers_count
        dimensions: List[int] = [dim for dim in range(self.input_dim, self.latent_dim, -dim_delta)]
        dimensions.append(self.latent_dim)

        encoder_modules: OrderedDict[str, nn.Module] = OrderedDict()
        decoder_modules: OrderedDict[str, nn.Module] = OrderedDict()
        for idx in range(1, len(dimensions)):
            reverse_idx = len(dimensions) - idx - 1
            encoder_modules[f'encode_linear_{idx}'] = nn.Linear(dimensions[idx - 1], dimensions[idx])
            decoder_modules[f'decode_linear_{idx}'] = nn.Linear(dimensions[reverse_idx + 1], dimensions[reverse_idx])
            if idx < len(dimensions) - 1:
                encoder_modules[f'encode_activation_{idx}'] = nn.ReLU()
                decoder_modules[f'decode_activation_{idx}'] = nn.ReLU()
        decoder_modules['decode_sigmoid'] = nn.Sigmoid()

        self._encoder = nn.Sequential(encoder_modules)
        self._decoder = nn.Sequential(decoder_modules)

        self._optimizer = optim.Adam(self.parameters(), lr=self.learning_rate, weight_decay=1e-5)
        self._criterion = nn.MSELoss()

    def forward(self, inputs):
        codes = self._encoder(inputs)
        decoded = self._decoder(codes)
        return codes, decoded

    def predict_encoder(self, inputs):
        return self._encoder(inputs)

    def predict_decoder(self, inputs):
        return self._decoder(inputs)

    def train_model(self, x):
        train_loader = DataLoader(x, batch_size=self.batch_size, shuffle=True)

        for epoch in range(self.epochs):
            for data in train_loader:
                inputs = data.view(-1, self.input_dim)
                # Predictions
                codes, decoded = self(inputs)
                # Calculate Loss
                loss = self._criterion(decoded, inputs)
                # Backpropagation
                self._optimizer.zero_grad()
                loss.backward()
                self._optimizer.step()

                print('epoch [{}/{}], loss:{:.4f}'
                      .format(epoch + 1, self.epochs, loss.data))
