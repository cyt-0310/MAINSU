"""Public endpoint checks only: no API key, portfolio, generation or billable call."""
import socket
import ssl
import sys
import urllib.error
import urllib.request

HOST = 'generativelanguage.googleapis.com'


def main():
    print('Gemini 網路檢查（不讀取金鑰、不上傳備審）', flush=True)
    print('系統代理設定：' + ('有' if urllib.request.getproxies() else '未偵測到'), flush=True)
    print('1/4 DNS 網址解析……', flush=True)
    try:
        socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        print('  成功', flush=True)
    except OSError as error:
        print('  失敗：' + type(error).__name__, flush=True)
        return 1
    print('2/4 直接連線到 API 的 443 連接埠……', flush=True)
    try:
        connection = socket.create_connection((HOST, 443), timeout=6)
    except OSError as error:
        print('  失敗：' + type(error).__name__ + '（代理網路可能不允許直接連線，仍會測試 HTTPS）', flush=True)
    else:
        print('  成功', flush=True)
        print('3/4 直接 TLS 加密握手……', flush=True)
        try:
            with connection:
                with ssl.create_default_context().wrap_socket(connection, server_hostname=HOST):
                    print('  成功', flush=True)
        except (OSError, ssl.SSLError) as error:
            print('  失敗：' + type(error).__name__, flush=True)
    print('4/4 HTTPS 回應測試（使用系統代理設定，不帶金鑰）……', flush=True)
    try:
        with urllib.request.urlopen('https://' + HOST + '/v1beta/models', timeout=8) as response:
            print(f'  已收到 HTTP {response.status}：API 網址可回應', flush=True)
    except urllib.error.HTTPError as error:
        print(f'  已收到 HTTP {error.code}：HTTPS 可取得回應；本測試未帶金鑰，不能判定帳號是否可用', flush=True)
    except (OSError, urllib.error.URLError) as error:
        cause = getattr(error, 'reason', error)
        print('  失敗：' + type(cause).__name__, flush=True)
        return 1
    print('檢查結束。網路可回應不等於模型、金鑰或額度已驗證。', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
