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
  --with-toolchain-type=gcc \
  --build=x86_64-unknown-linux-gnu \
  --host=x86_64-unknown-linux-gnu \
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
  --with-toolchain-type=gcc \
  --build=x86_64-unknown-linux-gnu \
  --host=x86_64-unknown-linux-gnu \
  --with-num-cores=1 \
  --with-jtreg=/opt/jtreg

make CONF=linux-x86_64-fastdebug images
```

检查结果：

```bash
build/linux-x86_64-fastdebug/images/jdk/bin/java -version
```

## 运行 controlledCrash 测试

release：

```bash
make CONF=linux-x86_64-release test \
  TEST="jtreg:test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java"
```

fastdebug：

```bash
make CONF=linux-x86_64-fastdebug test \
  TEST="jtreg:test/hotspot/jtreg/runtime/ErrorHandling/ControlledCrash.java"
```

两种配置的实际结果均为 `PASS 1、FAIL 0、ERROR 0`。一个测试文件内部依次检查编号 1 到 5。

## fastdebug 链接内存

本机在 WSL 只分配 2 GB 内存时，链接 `libjvm.so` 的 `ld` 进程被 OOM killer 结束。将 WSL 内存和 swap 分别调整为 8 GB 后，再次执行同一条 `make` 命令即可继续增量构建。

## 查看构建状态

实时看日志：

```bash
tail -f build/linux-x86_64-release/build.log
```

查看 fastdebug 时，将路径中的 `release` 改为 `fastdebug`。

查找错误：

```bash
grep -nE 'error:|Error [0-9]+|ERROR: Build failed' \
  build/linux-x86_64-release/build.log | tail -20
```

按 `Ctrl+C` 可以停止构建。再次执行同一个 `make` 命令会继续增量构建。
