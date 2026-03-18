cmake_minimum_required(VERSION 3.20)
project(Memoir VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)
find_package(cppwinrt CONFIG REQUIRED)
find_package(FFMPEG REQUIRED)

pybind11_add_module(Memoir
    src/bindings/module.cpp
    src/core/capture_engine.cpp
    src/core/keyboard.cpp
    src/core/window_finder.cpp
    src/recording/recording_session.cpp
)

target_include_directories(Memoir PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src
    ${FFMPEG_INCLUDE_DIRS}
)

target_link_libraries(Memoir PRIVATE
    Microsoft::CppWinRT
    d3d11
    dxgi
    windowsapp
    ${FFMPEG_LIBRARIES}
)

target_compile_definitions(Memoir PRIVATE NOMINMAX)

if(MSVC)
    target_compile_options(Memoir PRIVATE /bigobj)
endif()

# Post-build: copy FFmpeg DLLs and .pyd to project root for easy `import Memoir`
add_custom_command(TARGET Memoir POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        $<TARGET_FILE:Memoir>
        ${CMAKE_SOURCE_DIR}/Memoir.pyd
    COMMENT "Copying Memoir.pyd to project root"
)

file(GLOB _FFMPEG_DLLS "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/bin/av*.dll"
                       "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/bin/sw*.dll")
foreach(_dll ${_FFMPEG_DLLS})
    add_custom_command(TARGET Memoir POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${_dll}" ${CMAKE_SOURCE_DIR}
    )
endforeach()

if(_FFMPEG_DLLS)
    add_custom_command(TARGET Memoir POST_BUILD
        COMMENT "Copied FFmpeg DLLs to project root"
    )
endif()
