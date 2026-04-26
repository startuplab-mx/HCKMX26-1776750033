import mongoose, { Schema, Document } from 'mongoose';

interface ILocation {
  type: 'Point';
  coordinates: [number, number];
}

interface IBaseItem extends Document {
  source: 'youtube' | 'telegram' | 'tiktok';
  title?: string;
  description?: string;
  url?: string;
  location?: ILocation;
  engagement?: {
    views?: number;
    likes?: number;
    comments?: number;
    shares?: number;
  };
  createdAt: Date;
  updatedAt: Date;
}

const baseItemSchema = new Schema<IBaseItem>(
  {
    source: {
      type: String,
      enum: ['youtube', 'telegram', 'tiktok'],
      required: true,
      index: true,
    },
    title: String,
    description: String,
    url: String,
    location: {
      type: {
        type: String,
        enum: ['Point'],
      },
      coordinates: [Number],
    },
    engagement: {
      views: Number,
      likes: Number,
      comments: Number,
      shares: Number,
    },
  },
  { timestamps: true }
);

// Índice geoespacial para búsquedas de ubicación
baseItemSchema.index({ 'location.coordinates': '2dsphere' });

export const ContentItem = mongoose.model<IBaseItem>('ContentItem', baseItemSchema);

interface ITelegramChannel extends Document {
  channel_id: string;
  name: string;
  description?: string;
  location?: ILocation;
  members?: number;
  createdAt: Date;
  updatedAt: Date;
}

const telegramChannelSchema = new Schema<ITelegramChannel>(
  {
    channel_id: {
      type: String,
      required: true,
      unique: true,
      index: true,
    },
    name: {
      type: String,
      required: true,
    },
    description: String,
    location: {
      type: {
        type: String,
        enum: ['Point'],
      },
      coordinates: [Number],
    },
    members: Number,
  },
  { timestamps: true }
);

telegramChannelSchema.index({ 'location.coordinates': '2dsphere' });

export const TelegramChannel = mongoose.model<ITelegramChannel>(
  'TelegramChannel',
  telegramChannelSchema
);
