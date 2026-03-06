FROM node:18-alpine

WORKDIR /app

# Install dependencies for native modules
RUN apk add --no-cache python3 make g++

COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com

COPY . .

CMD ["npm", "run", "dev"]
