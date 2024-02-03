# ---------------------------------
# --------人生苦短，我用python--------
# ---------------------------------
# ---------------------------------
# --------人生苦短，我用python--------
# ---------------------------------
import datetime
import itertools
import os
import re
import torch
import numpy as np
import pandas as pd
import requests

PAD_ID = 0


class DateData:
    def __init__(self):
        data_path = "./model_comparison_data50.txt"
        self.date_train = []  # 记录中国日期数据  例如 31-04-26
        self.date_target = []  # 记录外国日期数据  例如 26/Apr/2031
        self.vocab = set()
        # -------------------------------------产生训练数据 和 目标数据-------------------------------

        with open(data_path, 'r', encoding='iso-8859-1') as f:
            lines = f.read().split('\n')
        for line in lines:
            input_text, target_text = line.split('/-*/')
            if(len(input_text) != 50 or len(target_text) != 1):
                continue
            target_text = '\t' + target_text + '\n'
            self.date_train.append(input_text)
            self.date_target.append(target_text)
        # -------------------------------------产生训练数据 和 目标数据-------------------------------

        # ********************************************将数据向量化****************************************************************

            for char in input_text:
                if char not in self.vocab:
                    self.vocab.add(char)
            for char in target_text:
                if char not in self.vocab:
                    self.vocab.add(char)

        self.v2i = {v: i for i, v in enumerate(sorted(list(self.vocab)), start=1)}  # 字典  V代表数据 I代表对于索引   用于向量化
        # 注意sorted 为内嵌参数 ，不改变原来列表    而 sort 的使用 a.sort（）
        self.v2i["<PAD>"] = PAD_ID  # 给字典增加新的键值对,用于覆盖填充。
        self.vocab.add("<PAD>")
        self.i2v = {i: v for v, i in self.v2i.items()}  # 将字典v2i的键和值反转    用于将预测数据的 向量转化数据

        self.x, self.y = [], []
        for d_in, d_get in zip(self.date_train, self.date_target):  # 其实就是将这些序列中对应位置的元素重新组合，生成一个个新的元组。
            self.x.append([self.v2i[v] for v in d_in])
            self.y.append([self.v2i[v] for v in d_get])
        self.x = np.array(self.x)  # 列表中的列表转化为数组
        self.y = np.array(self.y)

        # ********************************************将数据向量化****************************************************************
        self.start_token = self.v2i["\t"]
        self.end_token = self.v2i["\n"]

    def sample(self, n=64):            # 在数据集种抽样
        bi = np.random.randint(0, len(self.x), size=n)
        bx, by = self.x[bi], self.y[bi]
        dec_input = [i[:2] for i in by]
        dec_output = [i[1:3] for i in by]
        dec_input = np.array(dec_input)
        dec_output = np.array(dec_output)
        return torch.LongTensor(bx), torch.LongTensor(dec_input), torch.LongTensor(dec_output)

    def idx2str(self, idx):
        x = []
        for i in idx:
            x.append(self.i2v[i])
            if i == self.end_token:
                break
        return "".join(x)  # join()连接任意数量的字符串。

    @property
    def num_word(self):
        return len(self.vocab)


def pad_zero(seqs, max_len):     # 将矩阵（X，y）转化为（X，max_len）
    padded = np.full((len(seqs), max_len), fill_value=PAD_ID, dtype=np.long)     # len(seqs)  是将seqs看成 列表元素为列表 的列表
    for i, seq in enumerate(seqs):
        padded[i, :len(seq)] = seq
    return padded


def maybe_download_mrpc(save_dir="./MRPC/", proxy=None):
    train_url = 'https://mofanpy.com/static/files/MRPC/msr_paraphrase_train.txt'
    test_url = 'https://mofanpy.com/static/files/MRPC/msr_paraphrase_test.txt'
    os.makedirs(save_dir, exist_ok=True)
    proxies = {"http": proxy, "https": proxy}
    for url in [train_url, test_url]:
        raw_path = os.path.join(save_dir, url.split("/")[-1])
        if not os.path.isfile(raw_path):
            print("downloading from %s" % url)
            r = requests.get(url, proxies=proxies)
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(r.text.replace('"', "<QUOTE>"))
                print("completed")


def _text_standardize(text):
    text = re.sub(r'—', '-', text)
    text = re.sub(r'–', '-', text)
    text = re.sub(r'―', '-', text)
    text = re.sub(r" \d+(,\d+)?(\.\d+)? ", " <NUM> ", text)
    text = re.sub(r" \d+-+?\d*", " <NUM>-", text)
    return text.strip()


def _process_mrpc(dir="./MRPC", rows=None):
    data = {"train": None, "test": None}
    files = os.listdir(dir)
    for f in files:
        df = pd.read_csv(os.path.join(dir, f), sep='\t', nrows=rows)
        k = "train" if "train" in f else "test"
        data[k] = {"is_same": df.iloc[:, 0].values, "s1": df["#1 String"].values, "s2": df["#2 String"].values}
    vocab = set()
    for n in ["train", "test"]:
        for m in ["s1", "s2"]:
            for i in range(len(data[n][m])):
                data[n][m][i] = _text_standardize(data[n][m][i].lower())
                cs = data[n][m][i].split(" ")
                vocab.update(set(cs))
    v2i = {v: i for i, v in enumerate(sorted(vocab), start=1)}
    v2i["<PAD>"] = PAD_ID
    v2i["<MASK>"] = len(v2i)
    v2i["<SEP>"] = len(v2i)
    v2i["<GO>"] = len(v2i)
    i2v = {i: v for v, i in v2i.items()}
    for n in ["train", "test"]:
        for m in ["s1", "s2"]:
            data[n][m + "id"] = [[v2i[v] for v in c.split(" ")] for c in data[n][m]]
    return data, v2i, i2v


class MRPCData:
    num_seg = 3
    pad_id = PAD_ID

    def __init__(self, data_dir="./MRPC/", rows=None, proxy=None):
        maybe_download_mrpc(save_dir=data_dir, proxy=proxy)
        data, self.v2i, self.i2v = _process_mrpc(data_dir, rows)
        self.max_len = max(
            [len(s1) + len(s2) + 3 for s1, s2 in zip(
                data["train"]["s1id"] + data["test"]["s1id"], data["train"]["s2id"] + data["test"]["s2id"])])

        self.xlen = np.array([
            [
                len(data["train"]["s1id"][i]), len(data["train"]["s2id"][i])
            ] for i in range(len(data["train"]["s1id"]))], dtype=int)
        x = [
            [self.v2i["<GO>"]] + data["train"]["s1id"][i] + [self.v2i["<SEP>"]] + data["train"]["s2id"][i] + [
                self.v2i["<SEP>"]]
            for i in range(len(self.xlen))
        ]
        self.x = pad_zero(x, max_len=self.max_len)
        self.nsp_y = data["train"]["is_same"][:, None]

        self.seg = np.full(self.x.shape, self.num_seg - 1, np.int32)
        for i in range(len(x)):
            si = self.xlen[i][0] + 2
            self.seg[i, :si] = 0
            si_ = si + self.xlen[i][1] + 1
            self.seg[i, si:si_] = 1

        self.word_ids = np.array(list(set(self.i2v.keys()).difference(
            [self.v2i[v] for v in ["<PAD>", "<MASK>", "<SEP>"]])))

    def sample(self, n):
        bi = np.random.randint(0, self.x.shape[0], size=n)
        bx, bs, bl, by = self.x[bi], self.seg[bi], self.xlen[bi], self.nsp_y[bi]
        return bx, bs, bl, by

    @property
    def num_word(self):
        return len(self.v2i)

    @property
    def mask_id(self):
        return self.v2i["<MASK>"]


class MRPCSingle:
    pad_id = PAD_ID

    def __init__(self, data_dir="./MRPC/", rows=None, proxy=None):
        maybe_download_mrpc(save_dir=data_dir, proxy=proxy)
        data, self.v2i, self.i2v = _process_mrpc(data_dir, rows)

        self.max_len = max([len(s) + 2 for s in data["train"]["s1id"] + data["train"]["s2id"]])
        x = [
            [self.v2i["<GO>"]] + data["train"]["s1id"][i] + [self.v2i["<SEP>"]]
            for i in range(len(data["train"]["s1id"]))
        ]
        x += [
            [self.v2i["<GO>"]] + data["train"]["s2id"][i] + [self.v2i["<SEP>"]]
            for i in range(len(data["train"]["s2id"]))
        ]
        self.x = pad_zero(x, max_len=self.max_len)
        self.word_ids = np.array(list(set(self.i2v.keys()).difference([self.v2i["<PAD>"]])))

    def sample(self, n):
        bi = np.random.randint(0, self.x.shape[0], size=n)
        bx = self.x[bi]
        return bx

    @property
    def num_word(self):
        return len(self.v2i)


class Dataset:
    def __init__(self, x, y, v2i, i2v):
        self.x, self.y = x, y
        self.v2i, self.i2v = v2i, i2v
        self.vocab = v2i.keys()

    def sample(self, n):
        b_idx = np.random.randint(0, len(self.x), n)
        bx, by = self.x[b_idx], self.y[b_idx]
        return bx, by

    @property
    def num_word(self):
        return len(self.v2i)


def process_w2v_data(corpus, skip_window=2, method="skip_gram"):
    all_words = [sentence.split(" ") for sentence in corpus]
    all_words = np.array(list(itertools.chain(*all_words)))
    # vocab sort by decreasing frequency for the negative sampling below (nce_loss).
    vocab, v_count = np.unique(all_words, return_counts=True)
    vocab = vocab[np.argsort(v_count)[::-1]]

    print("all vocabularies sorted from more frequent to less frequent:\n", vocab)
    v2i = {v: i for i, v in enumerate(vocab)}
    i2v = {i: v for v, i in v2i.items()}

    # pair data
    pairs = []
    js = [i for i in range(-skip_window, skip_window + 1) if i != 0]

    for c in corpus:
        words = c.split(" ")
        w_idx = [v2i[w] for w in words]
        if method == "skip_gram":
            for i in range(len(w_idx)):
                for j in js:
                    if i + j < 0 or i + j >= len(w_idx):
                        continue
                    pairs.append((w_idx[i], w_idx[i + j]))  # (center, context) or (feature, target)
        elif method.lower() == "cbow":
            for i in range(skip_window, len(w_idx) - skip_window):
                context = []
                for j in js:
                    context.append(w_idx[i + j])
                pairs.append(context + [w_idx[i]])  # (contexts, center) or (feature, target)
        else:
            raise ValueError
    pairs = np.array(pairs)
    print("5 example pairs:\n", pairs[:5])
    if method.lower() == "skip_gram":
        x, y = pairs[:, 0], pairs[:, 1]
    elif method.lower() == "cbow":
        x, y = pairs[:, :-1], pairs[:, -1]
    else:
        raise ValueError
    return Dataset(x, y, v2i, i2v)  # 数据向量化


def set_soft_gpu(soft_gpu):
    import tensorflow as tf
    if soft_gpu:
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            # Currently, memory growth needs to be the same across GPUs
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            logical_gpus = tf.config.experimental.list_logical_devices('GPU')
            print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")  # 设置Gpu
