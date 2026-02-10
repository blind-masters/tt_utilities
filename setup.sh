#!/bin/bash
MAIN_SCRIPT="main.py"
REQUIREMENTS_FILE="requirements-linux.txt"
SDK_DOWNLOADER_SCRIPT="downloader.py"

set -e
cd "$(dirname "$0")"

C_GREEN='\033[0;32m'
C_RED='\033[0;31m'
C_YELLOW='\033[0;33m'
C_BOLD='\033[1m'
C_RESET='\033[0m'

print_step() {
    echo -e "\n${C_BOLD}${C_GREEN}>> Step ${1}:${C_RESET}${C_BOLD} ${2}${C_RESET}"
}

# Prints a success message
print_success() {
    echo -e "${C_GREEN}✔ ${1}${C_RESET}"
}

# Prints an error message and exits
print_error() {
    echo -e "\n${C_RED}✖ ERROR: ${1}${C_RESET}"
    echo -e "${C_YELLOW}Setup cannot continue. Please fix the issue and run the script again.${C_RESET}"
    exit 1
}

main() {
    clear
    echo -e "${C_BOLD}Welcome to the TT Utilities Bot Setup${C_RESET}"
    echo
    echo "This script will check for required software, install any missing components,"
    echo "and configure the bot for you."
    echo
    read -p "Press [Enter] to begin the setup..."
    clear

    print_step "1 of 5" "Checking system dependencies..."
    if [ ! -f /etc/os-release ]; then
        print_error "Cannot determine Linux distribution. /etc/os-release not found."
    fi
    # shellcheck source=/dev/null
    . /etc/os-release
    if [[ "$ID" == "debian" || "$ID" == "ubuntu" ]]; then
        PACKAGES="pulseaudio libmpv-dev mpv ffmpeg python3 python3-dev python3-pip git p7zip-full"
        echo "Updating package list..."
        sudo apt-get update -qq
        echo "Installing: ${PACKAGES}..."
        sudo apt-get install -y -qq ${PACKAGES}
        print_success "System dependencies are installed."
    else
        echo -e "${C_YELLOW}Warning: Non-Debian based distribution ('${ID}') detected.${C_RESET}"
        echo "Please ensure the following packages (or equivalents) are installed:"
        echo "pulseaudio, libmpv-dev, mpv, ffmpeg, python3, pip, git, 7zip"
        read -p "Press [Enter] to continue if they are installed, or Ctrl+C to exit."
    fi

    print_step "2 of 5" "Installing Python libraries..."
    if [ ! -f "${REQUIREMENTS_FILE}" ]; then
        print_error "'${REQUIREMENTS_FILE}' not found."
    fi
    echo "This may take a few moments..."
    if ! python3 -m pip install -r "${REQUIREMENTS_FILE}" -q --no-input; then
        print_error "Failed to install Python libraries. Try running 'pip3 install -r ${REQUIREMENTS_FILE}' manually."
    fi
    print_success "Python libraries installed successfully."

    print_step "3 of 5" "Configuring the TeamTalk SDK..."
    if [ ! -f "${SDK_DOWNLOADER_SCRIPT}" ]; then
        print_error "SDK downloader script ('${SDK_DOWNLOADER_SCRIPT}') not found."
    fi
    if ! python3 "${SDK_DOWNLOADER_SCRIPT}"; then
        print_error "The TeamTalk SDK download script failed."
    fi
    print_success "TeamTalk SDK configured successfully."

    print_step "4 of 5" "Configuring service installation..."
    INSTALL_TYPE=""
    while [[ -z "$INSTALL_TYPE" ]]; do
        read -p "Install services system-wide or for the current user? [system/user]: " choice
        case "$choice" in
            s|S|system|SYSTEM) INSTALL_TYPE="system" ;;
            u|U|user|USER) INSTALL_TYPE="user" ;;
            *) echo -e "${C_YELLOW}Invalid input. Please enter 'system' or 'user'.${C_RESET}" ;;
        esac
    done

    print_step "5 of 5" "Finalizing installation..."
    if [ "$INSTALL_TYPE" == "user" ]; then
        SERVICE_DIR="$HOME/.config/systemd/user"
        SYSTEMCTL_CMD="systemctl --user"
        echo "Configuring services for the current user ($USER)..."
        # Enable lingering to allow user services to run after logout
        if ! sudo loginctl show-user "$USER" | grep -q "Linger=yes"; then
            echo "Enabling user lingering..."
            sudo loginctl enable-linger "$USER"
        fi
        mkdir -p "${SERVICE_DIR}"
        cp systemd/user/*.service "${SERVICE_DIR}/"
        cp systemd/user/pulseaudio.socket "${SERVICE_DIR}/"
    else
        SERVICE_DIR="/etc/systemd/system"
        SYSTEMCTL_CMD="sudo systemctl"
        echo "Configuring system-wide services..."
        sudo cp systemd/user/*.* "${SERVICE_DIR}/"
    fi
    
    echo "Installing TeamTalk library..."
    sudo cp TeamTalk_DLL/libTeamTalk5.so /usr/lib/
    sudo ldconfig

    echo "Reloading systemd and enabling services..."
    $SYSTEMCTL_CMD daemon-reload
    $SYSTEMCTL_CMD enable --now pulseaudio.service pulseaudio.socket
    print_success "Services have been configured and started."

    echo
    echo -e "  Setup is Complete!"
    echo
    echo "The bot is now ready to be launched."
    echo "You can start it by running the following command:"
    echo -e "  ${C_YELLOW}python3 ${MAIN_SCRIPT}${C_RESET}"
    echo
}

main "$@"
