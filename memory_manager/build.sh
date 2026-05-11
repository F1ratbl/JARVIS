#!/usr/bin/env bash
# ═══════════════════════════════════════════
# 🤖 JARVIS — C++ Bellek Yönetim Modülü
# Tek komutla derleme betiği
#
# Kullanım:
#   chmod +x build.sh
#   ./build.sh          # Normal derleme
#   ./build.sh clean    # Temiz derleme (build/ sil + baştan derle)
#   ./build.sh debug    # Debug modda derle
# ═══════════════════════════════════════════

set -e  # Hata olursa dur

# Renkli çıktı
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
BUILD_TYPE="Release"

echo -e "${CYAN}"
echo "════════════════════════════════════════"
echo "  🤖 JARVIS — Memory Manager Derleme"
echo "════════════════════════════════════════"
echo -e "${NC}"

# ── Argümanlar ──
if [ "$1" = "clean" ]; then
    echo -e "${YELLOW}🧹 Temiz derleme — build/ siliniyor...${NC}"
    rm -rf "${BUILD_DIR}"
    # Eski .so/.dylib dosyalarını da temizle
    rm -f "${SCRIPT_DIR}"/_memory_manager*.so
    rm -f "${SCRIPT_DIR}"/_memory_manager*.dylib
fi

if [ "$1" = "debug" ]; then
    BUILD_TYPE="Debug"
    echo -e "${YELLOW}🐛 Debug modda derleniyor...${NC}"
fi

# ── Gereksinim kontrolü ──
echo -e "${CYAN}📋 Gereksinimler kontrol ediliyor...${NC}"

# CMake
if ! command -v cmake &> /dev/null; then
    echo -e "${RED}❌ CMake bulunamadı!${NC}"
    echo "   macOS:  brew install cmake"
    echo "   Linux:  sudo apt install cmake"
    exit 1
fi
echo -e "  ${GREEN}✅ CMake: $(cmake --version | head -n1)${NC}"

# Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Python bulunamadı!${NC}"
    exit 1
fi
echo -e "  ${GREEN}✅ Python: $(${PYTHON_CMD} --version)${NC}"

# pybind11
if ! ${PYTHON_CMD} -c "import pybind11" 2>/dev/null; then
    echo -e "${YELLOW}📦 pybind11 kuruluyor...${NC}"
    ${PYTHON_CMD} -m pip install pybind11
fi
echo -e "  ${GREEN}✅ pybind11: $(${PYTHON_CMD} -c "import pybind11; print(pybind11.__version__)")${NC}"

# ── Derleme ──
echo ""
echo -e "${CYAN}🔨 Derleniyor (${BUILD_TYPE})...${NC}"

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

cmake "${SCRIPT_DIR}" \
    -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DPython3_EXECUTABLE="$(which ${PYTHON_CMD})"

cmake --build . --config "${BUILD_TYPE}" -j "$(nproc 2>/dev/null || sysctl -n hw.ncpu)"

# Editörler (VS Code vb.) için compile_commands.json dosyasını ana dizine linkle
if [ -f "${BUILD_DIR}/compile_commands.json" ]; then
    ln -sf "${BUILD_DIR}/compile_commands.json" "${SCRIPT_DIR}/compile_commands.json"
fi

# ── Sonuç kontrolü ──
echo ""

# Derlenen dosyayı bul
COMPILED=$(find "${SCRIPT_DIR}" -name "_memory_manager*.so" -o -name "_memory_manager*.dylib" 2>/dev/null | head -1)

if [ -n "${COMPILED}" ] && [ -f "${COMPILED}" ]; then
    FILE_SIZE=$(du -h "${COMPILED}" | cut -f1)
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ Derleme başarılı!${NC}"
    echo -e "${GREEN}  📦 Dosya: $(basename "${COMPILED}") (${FILE_SIZE})${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""

    # Hızlı test
    echo -e "${CYAN}🧪 Hızlı test...${NC}"
    cd "${SCRIPT_DIR}/.."
    ${PYTHON_CMD} -c "
from memory_manager import MemoryManager, ModelProfiler, CacheController
print('  ✅ Import başarılı')
print(f'  {MemoryManager.summary()}')
mp = ModelProfiler()
print(f'  Whisper önerisi: {mp.recommend_whisper_model()}')
print(f'  LLM önerisi: {mp.recommend_llm_model()}')
cc = CacheController()
cc.mark_loaded('whisper', 500)
cc.mark_loaded('tts', 1200)
print(f'  CacheController: {cc.size()} modül yüklü')
print(f'  Boşaltma adayları: {cc.get_unload_candidates()}')
print()
print('  🎉 Tüm testler geçti!')
" 2>&1 || echo -e "${YELLOW}  ⚠️  Test çalıştırılamadı, ama modül derlendi.${NC}"
else
    echo -e "${RED}════════════════════════════════════════${NC}"
    echo -e "${RED}  ❌ Derleme başarısız!${NC}"
    echo -e "${RED}════════════════════════════════════════${NC}"
    exit 1
fi
