from torch import nn
import torch
import torch.nn.functional as F
from torch.nn.utils.rnn import pack_padded_sequence
from settings import HIDDEN_SIZE, DROPOUT, RNN

# #######################
# Luong attention layer #
# #######################


class LuongAttention(nn.Module):
    def __init__(self, method, hidden_size):
        super(LuongAttention, self).__init__()
        self.method = method
        if self.method not in ['dot', 'fullyconnected', 'concat']:
            raise ValueError(
                f"""{self.method} is not an appropriate attention method.\n
                    Options are: dot, fullyconnected, concat """
            )
        self.hidden_size = hidden_size
        if self.method == 'fullyconnected':
            self.attn = nn.Linear(self.hidden_size, hidden_size)
        elif self.method == 'concat':
            self.attn = nn.Linear(self.hidden_size * 2, hidden_size)
            self.v = nn.Parameter(torch.FloatTensor(hidden_size))

    def dot_score(self, hidden, encoder_output):
        return torch.sum(hidden * encoder_output, dim=2)

    def fullyconnected_score(self, hidden, encoder_output):
        energy = self.attn(encoder_output)
        return torch.sum(hidden * energy, dim=2)

    def concat_score(self, hidden, encoder_output):
        energy = self.attn(
            torch.cat((hidden.expand(encoder_output.size(0), -1, -1),
                       encoder_output), 2)).tanh()

        return torch.sum(self.v * energy, dim=2)

    def forward(self, hidden, encoder_outputs):
        # Calculate the attention weights (energies) based on the given method
        if self.method == 'fullyconnected':
            attn_energies = self.fullyconnected_score(hidden, encoder_outputs)
        elif self.method == 'concat':
            attn_energies = self.concat_score(hidden, encoder_outputs)
        elif self.method == 'dot':
            attn_energies = self.dot_score(hidden, encoder_outputs)

        # Transpose max_length and batch_size dimensions
        # attn_energies = attn_energies.t()
        # Return the softmax normalizedprobability scores(with added dimension)
        return F.softmax(attn_energies, dim=1)


class SacadeRnn(nn.Module):
    def __init__(self, nb_user, hidden_size=HIDDEN_SIZE, n_layers=1,
                 dropout=DROPOUT):
        super(SacadeRnn, self).__init__()
        self.n_layers = n_layers
        self.hidden_size = hidden_size
        # self.embedding = nn.Embedding(nb_user, hidden_size)
        # if dropout > 0:
        #     self.embedding_dropout = nn.Dropout(dropout)

        self.attn = LuongAttention("concat", self.hidden_size)
        if RNN == "LSTM":
            self.rnn1 = nn.LSTM(64, hidden_size, n_layers,
                                dropout=(0 if n_layers == 1 else 0),
                                bidirectional=True)

            self.rnn2 = nn.LSTM(hidden_size, hidden_size, n_layers,
                                dropout=(0 if n_layers == 1 else 0),
                                bidirectional=True)
        elif RNN == "GRU":
            self.rnn1 = nn.GRU(64, hidden_size, n_layers,
                               dropout=(0 if n_layers == 1 else 0),
                               bidirectional=True)

            self.rnn2 = nn.GRU(hidden_size, hidden_size, n_layers,
                               dropout=(0 if n_layers == 1 else 0),
                               bidirectional=True)

    def forward(self, sessions, lengths, hidden=None):
        # Convert word indexes to embeddings
        # embedded = self.embedding(input_seq)
        # if self.embedding_dropout:
        #     embedded = self.embedding_dropout(embedded)
        # Pack padded batch of sequences for RNN module
        # Allows pytorch to NOT compute padded elements
        # packed = nn.utils.rnn.pack_padded_sequence(embedded, input_lengths)
        # Forward pass through GRU
        # print("PLOP PLOP :    ", sessions.size())
        # print("KOUKOU : ", lengths)
        # packed = pack_padded_sequence(sessions, lengths, enforce_sorted=False)
        # print(packed)
        if RNN == "LSTM":
            outputs, (hidden, cells) = self.rnn1(sessions)
            # print("MOOO :  ", outputs)
        elif RNN == "GRU":
            outputs, hidden = self.gru1(outputs)
        # outputs, _ = nn.utils.rnn.pad_packed_sequence(outputs)
        # print("BWABWA  ", outputs)

        outputs = outputs[:, :, :self.hidden_size] + \
            outputs[:, :, self.hidden_size:]

        hidden = torch.sum(hidden, dim=0).unsqueeze(0)
        attn_weights = self.attn(hidden, outputs)
        outputs = outputs * attn_weights.unsqueeze(-1).repeat(1, 1,
                                                              self.hidden_size)

        # packed = pack_padded_sequence(outputs, lengths, enforce_sorted=False)
        outputs, hidden = self.rnn2(outputs)
        return torch.sum(outputs, dim=0)


class Classifier(nn.Module):
    def __init__(self, nb_user, dropout=0.2):
        super(Classifier, self).__init__()
        self.fc1 = nn.Linear(HIDDEN_SIZE*2, HIDDEN_SIZE)
        self.fc2 = nn.Linear(HIDDEN_SIZE, nb_user)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x, hidden=None):
        out = F.selu(self.dropout(self.fc1(x)))
        # out = F.softmax(self.fc2(out), dim=1)
        out = self.fc2(out)
        return out


class Autoencoder(nn.Module):
    def __init__(self, input_size, output_size, dropout=0.2):
        super(Autoencoder, self).__init__()
        compressed_size = input_size
        self.fc1 = nn.Linear(input_size, compressed_size)
        self.fc2 = nn.Linear(compressed_size, output_size)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x, hidden=None):
        out = F.selu(self.dropout(self.fc1(x)))
        out = F.selu(self.dropout(self.fc2(out)))
        return out


# class LuongAttnDecoderRNN(nn.Module):
#     def __init__(self, attn_model, embedding, hidden_size, output_size,
#                  n_layers=1, dropout=0.1):
#         super(LuongAttnDecoderRNN, self).__init__()

#         # Keep for reference
#         self.attn_model = attn_model
#         self.hidden_size = hidden_size
#         self.output_size = output_size
#         self.n_layers = n_layers
#         self.dropout = dropout

#         # Define layers
#         self.embedding = embedding
#         self.embedding_dropout = nn.Dropout(dropout)
#         self.gru = nn.GRU(hidden_size, hidden_size, n_layers,
#                           dropout=(0 if n_layers == 1 else dropout))
#         self.concat = nn.Linear(hidden_size * 2, hidden_size)
#         self.out = nn.Linear(hidden_size, output_size)

#         self.attn = Attn(attn_model, hidden_size)

#     def forward(self, input_step, last_hidden, encoder_outputs):
#         # Note: we run this one step (word) at a time
#         # Get embedding of current input word
#         embedded = self.embedding(input_step)
#         embedded = self.embedding_dropout(embedded)
#         # Forward through unidirectional GRU
#         rnn_output, hidden = self.gru(embedded, last_hidden)
#         # Calculate attention weights from the current GRU output
#         attn_weights = self.attn(rnn_output, encoder_outputs)
#         # Multiply attention weights to encoder outputs to get new
#         # "weighted sum" context vector
#         context = attn_weights.bmm(encoder_outputs.transpose(0, 1))
#         # Concatenate weighted context vector and GRU output using Luong eq. 5
#         rnn_output = rnn_output.squeeze(0)
#         context = context.squeeze(1)
#         concat_input = torch.cat((rnn_output, context), 1)
#         concat_output = torch.tanh(self.concat(concat_input))
#         # Predict next word using Luong eq. 6
#         output = self.out(concat_output)
#         output = F.softmax(output, dim=1)
#         # Return output and final hidden state
#         return output, hidden


# def maskNLLLoss(inp, target, mask):
#     nTotal = mask.sum()
#     crossEntropy = -torch.log(torch.gather(inp, 1, target.view(-1, 1)
#                                            ).squeeze(1))
#     loss = crossEntropy.masked_select(mask).mean()
#     return loss, nTotal.item()
