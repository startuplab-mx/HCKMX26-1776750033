import mongoose from 'mongoose';
import dns from 'node:dns';

// Work around local DNS resolvers that reject SRV queries used by mongodb+srv URIs.
dns.setServers(['8.8.8.8', '1.1.1.1']);

export const connectMongoDB = async () => {
  try {
    const mongoUri = process.env.MONGO_URI || 'mongodb://localhost:27017/centinela';

    await mongoose.connect(mongoUri, { dbName: 'golden' });
    console.log('✅ Conectado a MongoDB');
  } catch (error) {
    console.error('❌ Error conectando a MongoDB:', error);
    process.exit(1);
  }
};
