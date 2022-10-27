import os
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
from pytorch_lightning import LightningDataModule, LightningModule
from torchmetrics import Accuracy
from torchvision.datasets import MNIST
import hydra
from omegaconf import DictConfig
from pytorch_lightning import LightningModule, Trainer


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.5)
        self.fc1 = nn.Linear(9216, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = self.fc1(x)
        x = F.relu(x)
        x = self.dropout2(x)
        x = self.fc2(x)
        output = F.log_softmax(x, dim=1)
        return output


class ImageClassifier(LightningModule):
    def __init__(self, model=None, lr=1.0, gamma=0.7):
        super().__init__()
        self.save_hyperparameters(ignore="model")
        print(self.hparams)
        self.model = model or Net()
        self.val_acc = Accuracy()

        checkpoint_path = os.path.join(os.path.dirname(__file__), "demo_weights")
        if os.path.exists(checkpoint_path):
            self.load_state_dict(torch.load(checkpoint_path).state_dict())

    @property
    def example_input_array(self):
        return torch.zeros((1, 1, 28, 28))

    def forward(self, x):
        return self.model(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        logits = self.forward(x)
        loss = F.nll_loss(logits, y.long())
        self.log("train_loss", loss, on_step=True, on_epoch=True)
        return loss

    def validation_step(self, batch, batch_idx):
        x, y = batch
        logits = self.forward(x)
        loss = F.nll_loss(logits, y.long())
        self.log("val_acc", self.val_acc(logits, y))
        self.log("val_loss", loss)

    def configure_optimizers(self):
        return torch.optim.Adam(self.model.parameters(), lr=self.hparams.lr)

class MNISTDataModule(LightningDataModule):
    def __init__(self, batch_size: float = 32.0):
        super().__init__()
        self.batch_size = batch_size
        self.save_hyperparameters()

    @property
    def transform(self):
        return T.Compose([T.ToTensor(), T.Normalize((0.1307,), (0.3081,))])

    def prepare_data(self) -> None:
        should_download = True
        exists = os.path.exists("./data/MNIST/raw")
        if exists:
            should_download = len(os.listdir("./data/MNIST/raw")) != 8
        if should_download:
            MNIST("./data", download=True)

    def train_dataloader(self):
        train_dataset = MNIST("./data", train=True, download=False, transform=self.transform)
        return torch.utils.data.DataLoader(train_dataset, batch_size=int(self.hparams.batch_size))

    def val_dataloader(self):
        val_dataset = MNIST("./data", train=False, download=False, transform=self.transform)
        return torch.utils.data.DataLoader(val_dataset, batch_size=int(self.hparams.batch_size))

@hydra.main(config_path="configs", config_name="config")
def train(cfg: DictConfig):
    dm = MNISTDataModule(batch_size=cfg.data.batch_size)
    print(dm.batch_size)
    model = ImageClassifier()
    trainer = Trainer(accelerator="auto", devices="auto", max_epochs=3)
    trainer.fit(model, dm)

train()
