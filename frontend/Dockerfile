FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# مقادیر پیش‌فرض برای docker-compose محلی؛ روی پلتفرم‌هایی مثل Railway/Render
# با متغیر محیطی سرویس بازنویسی می‌شوند (PORT را خود پلتفرم معمولاً تزریق می‌کند)
ENV PORT=80
ENV BACKEND_ORIGIN=http://backend:8000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
