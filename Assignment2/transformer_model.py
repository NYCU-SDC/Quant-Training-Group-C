import torch
import torch.nn as nn

class transformer_block(nn.Module):
    def __init__(self, input_dim, embed_size, num_heads, drop_prob):
        super(transformer_block, self).__init__()
        self.embedding = nn.Linear(input_dim, embed_size)
        self.attention = nn.MultiheadAttention(embed_size, num_heads, batch_first=True)
        self.fc = nn.Sequential(nn.Linear(embed_size, 4 * embed_size),
                                nn.LeakyReLU(),
                                nn.Linear(4 * embed_size, embed_size))
        self.dropout = nn.Dropout(drop_prob)
        self.ln1 = nn.LayerNorm(embed_size, eps=1e-6)
        self.ln2 = nn.LayerNorm(embed_size, eps=1e-6)

    def forward(self, x):
        x = self.embedding(x)
        attn_out, _ = self.attention(x, x, x, need_weights=False)
        x = x + self.dropout(attn_out)
        x = self.ln1(x)

        fc_out = self.fc(x)
        x = x + self.dropout(fc_out)
        x = self.ln2(x)

        return x

class transformer_forecaster(nn.Module):
    def __init__(self, input_dim, embed_size, num_heads: list, drop_prob, num_classes = 3):
        super(transformer_forecaster, self).__init__()

        self.blocks = nn.ModuleList([transformer_block(input_dim, embed_size, num_heads[0], drop_prob)] +
                                    [transformer_block(embed_size, embed_size, num_heads[n], drop_prob) for n in range(1, len(num_heads))])

        self.weighted_sum = nn.Linear(embed_size, 1)

        self.forecast_head = nn.Sequential(nn.Linear(embed_size, embed_size * 2),
                                           nn.LeakyReLU(),
                                           nn.Dropout(drop_prob),
                                           nn.Linear(embed_size * 2, embed_size * 4),
                                           nn.LeakyReLU(),
                                           nn.Linear(embed_size * 4, num_classes),
                                           nn.ReLU())

    def forward(self, x_numeric):
        x = x_numeric
        # 經過Transformer Block
        for block in self.blocks:
            x = block(x)
        # attention weight
        attention_weights = self.weighted_sum(x)
        attention_weights = torch.softmax(attention_weights, dim=1)
        # weighted sum
        weighted_sum = torch.sum(attention_weights * x, dim=1)
        x = self.forecast_head(weighted_sum)
        # prob
        x = torch.softmax(x, dim = 1)

        return x

if __name__ == '__main__':
    # parameters
    input_dim = 5
    embed_size = 64
    num_heads = [4, 4, 4]
    drop_prob = 0.1
    num_classes = 3

    model = transformer_forecaster(input_dim, embed_size, num_heads, drop_prob, num_classes)
    batch_size = 1
    sequence_length = 10
    input_data = torch.randn(batch_size, sequence_length, input_dim)

    output = model(input_data)

    print(f"Input shape: {input_data.shape}")
    print(f"Output shape: {output}")