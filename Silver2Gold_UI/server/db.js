import mongoose from 'mongoose'

export async function connectToDatabase() {
  const mongoUri = process.env.MONGODB_URI

  if (!mongoUri) {
    return {
      connected: false,
      reason: 'Missing MONGODB_URI in environment variables',
    }
  }

  try {
    await mongoose.connect(mongoUri)
    return { connected: true }
  } catch (error) {
    return {
      connected: false,
      reason: error.message,
    }
  }
}

export function getDbConnectionState() {
  const states = {
    0: 'disconnected',
    1: 'connected',
    2: 'connecting',
    3: 'disconnecting',
  }

  return states[mongoose.connection.readyState] || 'unknown'
}
