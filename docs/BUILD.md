# 构建记录

下面的命令在 WSL Ubuntu 22.04 中执行，源码目录为 `~/TencentKona-25-master`。

## 环境检查

```bash
cd ~/TencentKona-25-master
command -v gcc g++ make autoconf
java -version
```

本次使用的 Boot JDK：

```text
/usr/lib/jvm/java-25-openjdk-amd64
```

## release

第一次配置：

```bash
bash configure \
  --with-boot-jdk=/usr/lib/jvm/java-25-openjdk-amd64 \
  --with-debug-level=release \
  --with-conf-name=linux-x86_64-release \
  --with-num-cores=1 \
  --with-jtreg=/opt/jtreg
```

开始或继续构建：

```bash
make CONF=linux-x86_64-release images
```

检查结果：

```bash
build/linux-x86_64-release/images/jdk/bin/java -version
```

## fastdebug

```bash
bash configure \
  --with-boot-jdk=/usr/lib/jvm/java-25-openjdk-amd64 \
  --with-debug-level=fastdebug \
  --with-conf-name=linux-x86_64-fastdebug \
  --with-num-cores=1 \
  --with-jtreg=/opt/jtreg

make CONF=linux-x86_64-fastdebug images
```

检查结果：

```bash
build/linux-x86_64-fastdebug/images/jdk/bin/java -version
```

## 查看构建状态

实时看日志：

```bash
tail -f build/linux-x86_64-release/build.log
```

查找错误：

```bash
grep -nE 'error:|Error [0-9]+|ERROR: Build failed' \
  build/linux-x86_64-release/build.log | tail -20
```

按 `Ctrl+C` 可以停止构建。再次执行同一个 `make` 命令会继续增量构建。
