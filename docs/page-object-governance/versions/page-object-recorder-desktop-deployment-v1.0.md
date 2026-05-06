# 页面对象录制桌面部署说明 V1.0

## 目标

生产环境中的 `web-ui-service` 需要能启动 Playwright codegen 录制窗口。Docker 容器默认没有图形桌面，因此需要为 `web-ui-service` 提供虚拟桌面能力。

本方案采用：

- `Xvfb`：提供虚拟 X11 Display
- `fluxbox`：提供轻量窗口管理器
- `x11vnc`：把 X11 桌面暴露为 VNC
- `noVNC`：让测试工程师通过浏览器查看和操作录制桌面

## 访问方式

Docker Compose 启动后，打开：

```text
http://localhost:6080/vnc.html
```

如果部署在服务器上，将 `localhost` 替换为服务器地址。

## 环境变量

```env
RECORDER_DESKTOP_ENABLED=true
RECORDER_DISPLAY=:99
RECORDER_SCREEN=1280x900x24
RECORDER_NOVNC_HOST_PORT=6080
RECORDER_VNC_PASSWORD=
```

生产环境建议设置：

```env
RECORDER_VNC_PASSWORD=your-strong-password
```

## 验收步骤

1. 重新构建并启动 web 服务：

```bash
docker compose up -d --build web nginx
```

2. 确认容器内 Display 存在：

```bash
docker exec ai-test-platform-web-1 sh -lc 'echo "$DISPLAY"; pgrep -af "Xvfb|fluxbox|x11vnc|websockify"'
```

3. 打开 noVNC：

```text
http://localhost:6080/vnc.html
```

4. 在平台页面对象录制页点击开始录制。

5. noVNC 桌面中应出现 Playwright codegen 窗口。

## 注意事项

- noVNC 端口不要直接暴露到公网。
- 如果必须远程访问，建议通过 VPN、堡垒机、内网网关或反向代理鉴权保护。
- 当前方案是让 `web-ui-service` 自带桌面能力。后续如果录制并发增加，建议拆成独立 `recorder-worker` 服务。
