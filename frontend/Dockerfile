FROM node:20-slim

WORKDIR /app

# Install dependencies for native modules
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

COPY . .

CMD ["npm", "run", "dev"]
