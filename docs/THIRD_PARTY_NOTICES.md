# 第三方组件许可

生产前端使用 React / React DOM（MIT）和 Lucide React（ISC），样式由 Tailwind CSS（MIT）构建；Vite、TypeScript、PostCSS、Autoprefixer用于构建。对应原许可文本在 docs/licenses 中。

后端及离线依赖使用 FastAPI、Starlette、Uvicorn、SQLAlchemy、Argon2 CFFI、Pydantic、OpenPyXL、Pillow、AnyIO、wsproto、tzdata及其依赖。每个随包wheel保留原始 `.dist-info` 元数据和许可文件，安装时一并安装。可打开wheel（ZIP格式）查看各组件许可证与版权。

PNG字体使用目标操作系统已安装的中文字体，不随包分发Windows字体。

Playwright只用于开发验收，安装浏览器时需遵循其组件许可；本交付不包含Chromium浏览器或开发机上的Playwright依赖目录。
