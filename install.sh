#! /bin/bash
script_dir=$(dirname "$(readlink -f "$0")")

mode="install"
if [ -n "$1" ]; then
    if [ "$1" == "update" ]; then
        mode="update"
    fi
fi

if [ "$mode" == "install" ]; then
    pip install argcomplete pyyaml
    activate-global-python-argcomplete
    cp $HOME/.bashrc $HOME/.bashrc.bak
    sed -i '/# >>> lightdds initialize >>>/,/# <<< lightdds initialize <<</d' "$HOME/.bashrc"
    echo "# >>> lightdds initialize >>>" >> ~/.bashrc
    echo "source $script_dir/setup.bash" >> ~/.bashrc
    echo "# <<< lightdds initialize <<<" >> ~/.bashrc
fi
chmod +x -R scripts/*
echo "export PATH=\$PATH:$script_dir/bin:$script_dir/scripts" > ./setup.bash
echo "export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:$script_dir/lib" >> ./setup.bash
echo "export DDS_INCLUDE_PATH=$script_dir/include" >> ./setup.bash
echo "export DDS_LIBRARY_PATH=$script_dir/lib" >> ./setup.bash
# source ~/.bashrc

# register argcomplete for bash in scripts
# first find all filename in scripts but not recursively
for file in $(find $script_dir/scripts -maxdepth 1 -type f); do
    # then register argcomplete for each file
    # get basename of file
    file=$(basename $file)
    echo $file
    echo "eval \"\$(register-python-argcomplete $file)\"" >> ./setup.bash
done

