# import tensorflow as tf
# print("TensorFlow version:", tf.__version__)
# print("Num GPUs Available: ", len(tf.config.list_physical_devices('GPU')))
# print("Num CPUs Available: ", len(tf.config.list_physical_devices('CPU')))
import tensorflow as tf
print("Num GPUs Available: ", len(tf.config.experimental.list_physical_devices('GPU')))
