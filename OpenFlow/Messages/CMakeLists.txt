add_library(Messages FeaturesDecoder.cpp)
add_library(FlowMatchDecoder FlowMatchDecoder.cpp)
add_library(FlowMatchEncoder FlowMatchEncoder.cpp)
add_library(FlowModActionEncoder FlowModActionEncoder.cpp)
add_library(FlowModEncoder FlowModEncoder.cpp)
add_library(FlowModInstructionEncoder FlowModInstructionEncoder.cpp)
add_library(HeaderDecoder HeaderDecoder.cpp)
add_library(HeaderEncoder HeaderEncoder.cpp)
add_library(HelloDecoder HelloDecoder.cpp)
add_library(OxmTLV OxmTLV.cpp)
add_library(PacketInDecoder PacketInDecoder.cpp)
add_library(FlowRemovedDecoder FlowRemovedDecoder.cpp)
target_link_libraries(Messages FlowMatchEncoder FlowMatchDecoder FlowModActionEncoder FlowModEncoder FlowModInstructionEncoder HelloDecoder OxmTLV PacketInDecoder HeaderDecoder HeaderEncoder FlowRemovedDecoder)
