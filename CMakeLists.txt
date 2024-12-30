cmake_minimum_required(VERSION 3.10)
project(RemoteControlClient)

set(CMAKE_CXX_STANDARD 11)

# Find the required packages
find_package(Threads REQUIRED)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# Add the executable
add_executable(RemoteControlClient client.cpp)

# Link the required libraries
target_link_libraries(RemoteControlClient ws2_32 ${CMAKE_THREAD_LIBS_INIT})
